"""
Convert UIMA CAS XMI data from Inception into TSV-format for the shared task.
This script is a customisation of the original script developed for Impresso
in the context of HIPE2020.
"""

import sys
import ipdb
from typing import Dict, Generator, List, Tuple
import argparse
import logging
from pathlib import Path
import csv
from collections import OrderedDict
from tqdm import tqdm
from typing import NamedTuple

from ajmc_utils import AjmcDocument, read_xmi, METADATA, HYPHENS
from impresso.helpers import compute_levenshtein_distance

from cassis import Cas, load_cas_from_xmi, load_typesystem

PARTIAL_FLAG = "Partial"
NO_SPACE_FLAG = "NoSpaceAfter"
END_OF_LINE_FLAG = "EndOfLine"
NIL_FLAG = "NIL"
LEVENSHTEIN_FLAG = "LED"

COL_LABELS = [
    "TOKEN",
    "NE-COARSE-LIT",
    "NE-COARSE-METO",
    "NE-FINE-LIT",
    "NE-FINE-METO",
    "NE-FINE-COMP",
    "NE-NESTED",
    "NEL-LIT",
    "NEL-METO",
    "MISC",
]

def parse_args():
    """Parse the arguments given with program call"""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i",
        "--dir_in",
        required=True,
        action="store",
        dest="dir_in",
        help="name of input dir where the xmi files are stored",
    )

    parser.add_argument(
        "-s",
        "--schema",
        required=True,
        action="store",
        dest="f_schema",
        help="path to the xml schema file",
    )

    parser.add_argument(
        "-l",
        "--log",
        action="store",
        default="clef_conversion.log",
        dest="f_log",
        help="name of log file",
    )

    parser.add_argument(
        "-o",
        "--dir_out",
        required=True,
        action="store",
        dest="dir_out",
        help="name of the output dir where the tsv files are stored",
    )
    """
    parser.add_argument(
        "-c",
        "--coref",
        action="store_true",
        dest="coref",
        help="include column with coreference annotation (not yet implemented)",
    )
    """

    parser.add_argument(
        "--drop_nested", action="store_true", help="drop information in nested column",
    )

    return parser.parse_args()


def index_inception_files(dir_data, suffix=".xmi") -> list:
    """Index all .xmi files in the provided directory

    :param type dir_data: Path to top-level dir.
    :param type suffix: Only consider files of this type.
    :return: List of found files.
    :rtype: list

    """

    return sorted([path for path in Path(dir_data).rglob("*" + suffix)])


def lookup_hyphenation(tok: dict, hyphenated_words: list, doc: AjmcDocument) -> Tuple:
    for word in hyphenated_words:
        if tok["start_offset"] <= word["start_offset"] < tok["end_offset"]:
            return (True, word['surface'])
        elif word["start_offset"] <= tok["start_offset"] < word["end_offset"]:
            return (True, word['surface'])
        else:
            return (False, None)
    return


def lookup_entity(tok: dict, mentions: dict, doc: AjmcDocument) -> Tuple:
    """Get the respective IOB-label of a named entity (NE).

    :param dict tok: Annotation of the token.
    :param dict mentions: Collections of annotated named entities.
    :param ImpressoDocument doc: Document with all the annotation information.
    :return: Nested Tuple comprising the entity with the longest span and the respective entity labels (coarse, fine_1, comp, literal, fine_2).
    :rtype: Tuple

    """

    matches = []

    for ent in mentions.values():
        if tok["start_offset"] <= ent["start_offset"] < tok["end_offset"]:
            # start of entity
            # entity may not match token boundaries
            # i.e. start/end in the middle of a token
            matches.append(("B", ent))
        elif ent["start_offset"] <= tok["start_offset"] < ent["end_offset"]:
            # token is part of an entity
            # inside of entity
            matches.append(("I", ent))

    # sort by the begin of the span and then by longest span
    # thus, the first match spans potential other matches
    matches = sorted(matches, key=lambda x: (x[1]["start_offset"], -x[1]["end_offset"]))

    # compounds = [(iob, ent) for iob, ent in matches if ent["entity_compound"]]
    compounds = []
    biblio = [(iob, ent) for iob, ent in matches if ent["entity_biblio"]]
    literals = [(iob, ent) for iob, ent in matches if ent["literal"] and not ent["entity_biblio"]]
    non_literals = [
        (iob, ent) for iob, ent in matches if not ent["literal"] and not ent["entity_compound"]
    ]

    n_nested = (
        len(matches) - min(len(compounds), 1) - min(len(non_literals), 1) - min(len(literals), 1)
    )
    if len(non_literals) > 1:
        # allow one nesting
        n_nested = n_nested - 1

    """
    # sanity checks
    if matches:
        ent_surface = matches[0][1]["surface"]
        if (literals or compounds) and not non_literals:
            msg = f"Token '{tok['surface']}' of entity '{ent_surface}' has no regular entity annotation (only compound or literal) in file {doc.filename}"
            logging.info(msg)
        if n_nested > 0:
            msg = f"Token '{tok['surface']}' of entity '{ent_surface}' has illegal entity overlappings (nesting) in file {doc.filename}"
            logging.info(msg)
    """

    return literals, non_literals, biblio


def assemble_entity_label(matches, level, nested=False) -> str:
    """
    Set label for an entity

    matches = [('B', {'entity_fine': '', 'start_offset': 15 ...})
              ...]
    """
    if not matches:
        label = "O"

    elif nested:
        if len(matches) > 1:
            # second entry corresponds to first nested entity below the main entity
            iob, ent = matches[1]
            label = f"{iob}-{ent[level]}"
        else:
            label = "O"

    elif matches[0][0] is None:
        label = "O"
    else:
        # first entry corresponds to longest entity span
        iob, ent = matches[0]
        label = f"{iob}-{ent[level]}"

    return label


def lookup_nel(
    token, entity, doc: AjmcDocument, strip_base: bool = True, discard_time_links: bool = True
) -> str:
    """Get the link to wikidata entry of a named entity (NE).

    :param dict token: Annotation of the token.
    :param dict entity: Annotation of the main entity to look up the link.
    :param AjmcDocument doc: Document with all the annotation information.
    :param bool strip_base: Keep only wikidata identifier instead of entire link.
    :param bool discard_time_links: Discard the wikidata link for time mentions even if present.
    :return: A Link to corresponding wikidata of the entity.
    :rtype: str

    """
    if entity:
        nel = doc.links[entity["id"]]

        # do sanity checks only once per named entity
        if entity["start_offset"] == token["start_offset"]:
            #validate_link(nel, entity, doc)
            pass

        link = nel["wikidata_id"] if nel["wikidata_id"] else NIL_FLAG

        #if discard_time_links and "time" in entity["entity_coarse"]:
        #    link = NIL_FLAG

        if strip_base:
            link = link.split("/")[-1]
    else:
        link = "_"

    return link


def get_document_metadata(doc: AjmcDocument) -> List[Dict]:
    """Set metadata on the level of segments (line).

    :param AjmcDocument doc: Document with all the annotation information.
    :return: Nested list with various metadata
    :rtype: [list]

    """
    commentary_id, page_number = doc.id.split("_")
    rows = []
    rows.append(["# document_id = " + doc.id])
    if commentary_id in METADATA:
        metadata = METADATA[commentary_id]
        fields = ["title", "author", "publication_date", "publication_place"]
        for field in fields:
            rows.append([f"# {field} = " + metadata[field]])
        rows.append([f"# page = {int(page_number)}"])
    return rows


def set_special_flags(
    tok: dict, seg: dict, ent_lit: dict, ent_meto: dict, doc: AjmcDocument
) -> str:
    """Set a special flags if token is hyphenated or not followed by a whitespace.

    :param dict tok: Annotation of the token.
    :param dict seg: Annotation of the segment.
    :param dict ent_lit: Annotation of the literal entity.
    :param dict ent_meto: Annotation of the metonymic entity.
    :param AjmcDocument doc: Document with all the annotation information.
    :return: Flags concatenated by a '|' and sorted alphabetically.
    :rtype: str

    """

    flags = []

    # set flag if there is no space after the token
    first_char_after_token = doc.text[tok["end_offset"] : tok["end_offset"] + 1]

    # case 1: no space directly after token
    # case 2: token is followed by a underscore
    # the second case is necessary as the underscore is use as a replacement symbol
    # for any control characters in the retokenization script
    if first_char_after_token != " " or first_char_after_token == "_":
        flags.append(NO_SPACE_FLAG)

    # set flag if token is at the end of a segment (line)
    if tok == seg["tokens"][-1]:
        flags.append(END_OF_LINE_FLAG)

    if ent_lit:
        # set flag if entity boundary doesn't match token boundary
        # e.g. Ruhrgebiet -> Ruhr is the entity
        # e.g. xxxParis -> Paris is the entity
        if (
            ent_lit["end_offset"] < tok["end_offset"]
            or ent_lit["start_offset"] > tok["start_offset"]
        ):
            start = ent_lit["start_offset"] - tok["start_offset"]
            end = min(len(tok["surface"]), ent_lit["end_offset"] - tok["start_offset"])
            flags.append(f"{PARTIAL_FLAG}-{start}:{end}")
        """
        try:
            # sometimes the transcript is recorded for the metonymic entity instead of the literal one
            levenshtein_dist = max(ent_lit["levenshtein_norm"], ent_meto["levenshtein_norm"])
        except TypeError:
            levenshtein_dist = ent_lit["levenshtein_norm"]

        flags.append(f"{LEVENSHTEIN_FLAG}{levenshtein_dist:.2f}")
        """

    if not flags:
        flags.append("_")

    # sort alphabetically, Levenshtein always last
    return "|".join(sorted(flags, key=lambda x: "Z" if "LED" in x else x))


def dehyphenate(tok: str) -> str:
    hyphen_position = None
    for char in HYPHENS:
        try:
            hyphen_position = tok.index(char)
        except ValueError:
            pass
    
    if hyphen_position:
        hyphen = tok[hyphen_position]
        dehyphenated_token = tok.replace(hyphen, "")
        logging.info(f"Hyphenation – Removed character {hyphen} from {tok} => {dehyphenated_token}")
        return dehyphenated_token
    else:
        logging.info(f"Hyphenation – No hyphen detected in {tok}")
        return tok




def convert_data(doc: AjmcDocument, drop_nested: bool) -> List:
    """Select the relevant annotations per token for the finegrained format.

    :param ImpressoDocument doc: Document with all the annotation information.
    :param bool drop_nested: Drop annotation of nested entities and replace with underscore.
    :return: A nested list of tokens and its annotations.
    :rtype: [list]

    """

    rows = []
    biblio_rows = []

    rows += get_document_metadata(doc)

    for i_seg, seg in enumerate(doc.sentences.values()):

        is_prev_token_hyphenated = False

        for i_tok, tok in enumerate(seg["tokens"]):

            literals, non_literals, biblio = lookup_entity(tok, doc.mentions, doc)
            is_hyphenated, hyphenated_form = lookup_hyphenation(tok, doc.hyphenated_words, doc)

            token_surface = tok["surface"]

            if is_hyphenated:
                if is_prev_token_hyphenated:
                    continue
                else:
                    token_surface = dehyphenate(hyphenated_form)
                    is_prev_token_hyphenated = True
            else:
                is_prev_token_hyphenated = False


            if drop_nested:
                fine_2 = "_"
            else:
                fine_2 = assemble_entity_label(literals, "entity_fine", nested=True)

            # set literal annotation as default if there is no metonymic annotation
            if not literals:
                literals = non_literals
                non_literals = []

            # prevent overwriting of ongoing standard annotation by an explicit literal annotation
            try:
                # prevent overwriting of ongoing standard annotation by a explicit literal annotation
                if non_literals[0][1]["start_offset"] < literals[0][1]["start_offset"]:
                    literals.insert(0, non_literals[0])
                    non_literals[0] = (None, None)
            except IndexError:
                # no precende of metonymic as there are no annotations
                pass

            # we don't have metonimy in our dataset
            coarse_meto = "_"
            coarse_lit = assemble_entity_label(literals, "entity_coarse")
            fine_meto = "_"
            fine_lit = assemble_entity_label(literals, "entity_fine")
            comp = "_"
            

            # set longest entity span for literal and non-literal (metonymic)
            # to look up NEL
            main_ent_nonlit = non_literals[0][1] if non_literals else None
            main_ent_lit = literals[0][1] if literals else None

            nel_nonlit = lookup_nel(tok, main_ent_nonlit, doc)
            nel_lit = lookup_nel(tok, main_ent_lit, doc)

            misc = set_special_flags(tok, seg, main_ent_lit, main_ent_nonlit, doc)

            row = [
                token_surface,
                coarse_lit,
                coarse_meto,
                fine_lit,
                fine_meto,
                comp,
                fine_2,  # nested
                nel_lit,
                nel_nonlit,
                misc,
            ]

            coarse_meto = "_"
            coarse_lit = assemble_entity_label(biblio, "entity_biblio")
            fine_meto = "_"
            fine_lit = "_"
            fine_2 = "_"
            comp = "_"
            nel_lit = "_"
            nel_nonlit = "_"

            biblio_row = [
                token_surface,
                coarse_lit,
                coarse_meto,
                fine_lit,
                fine_meto,
                comp,
                fine_2,  # nested
                nel_lit,
                nel_nonlit,
                misc,
            ]

            rows.append(row)
            biblio_rows.append(biblio_row)
    #ipdb.set_trace()
    return rows, biblio_rows


def start_batch_conversion(
    dir_in: str, dir_out: str, f_schema: str, coref: bool = False, drop_nested: bool = False
):
    """Start a batch conversion of xmi files in the given folder .

    :param str dir_in: Top-level folder containing the .xmi-files.
    :param str dir_out: Top-level output folder for the converted documents.
    :param str f_schema: Path to the .XML-file of the schema.
    :param bool coref: Add information of coreference cluster (not yet implemented).
    :param bool drop_nested: Drop annotation of nested entities and replace with underscore.
    :return: None.
    :rtype: None

    """

    xmi_files = index_inception_files(dir_in)
    tsv_files = [Path(str(p).replace(dir_in, dir_out)).with_suffix(".tsv") for p in xmi_files]
    tsv_biblio_files = [Path(str(f).replace('.tsv', '-biblio.tsv')) for f in tsv_files]
    msg = f"Start conversion of {len(xmi_files)} files."
    logging.info(msg)
    print(msg)

    for f_xmi, f_tsv, f_biblio_tsv in tqdm(list(zip(xmi_files, tsv_files, tsv_biblio_files))):

        info_msg = f"Converting {f_xmi} into {f_tsv}"
        logging.info(info_msg)

        doc = read_xmi(f_xmi, f_schema, sanity_check=False)
        f_tsv.parent.mkdir(parents=True, exist_ok=True)

        data, biblio_data = convert_data(doc, drop_nested)

        with f_tsv.open("w") as tsvfile:
            writer = csv.writer(tsvfile, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar="")
            writer.writerow(COL_LABELS)
            writer.writerows(data)

        with f_biblio_tsv.open("w") as tsvfile:
            writer = csv.writer(tsvfile, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar="")
            writer.writerow(COL_LABELS)
            writer.writerows(biblio_data)

    logging.info(f"Conversion completed.")

def main():

    args = parse_args()

    logging.basicConfig(
        filename=args.f_log,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    start_batch_conversion(args.dir_in, args.dir_out, args.f_schema, args.drop_nested)


################################################################################
if __name__ == "__main__":
    main()