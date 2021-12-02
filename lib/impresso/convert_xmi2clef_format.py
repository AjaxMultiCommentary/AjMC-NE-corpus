"""
Convert UIMA CAS XMI data from Inception into TSV-format for the shared task
"""

import sys

from typing import Generator, List, Tuple
import argparse
import logging
from pathlib import Path
import csv
from collections import OrderedDict
from tqdm import tqdm
from typing import NamedTuple

from helpers import ImpressoDocument, compute_levenshtein_distance

from cassis import Cas, load_cas_from_xmi, load_typesystem


sys.path.append("../../impresso_evaluation")

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

    parser.add_argument(
        "-c",
        "--coref",
        action="store_true",
        dest="coref",
        help="include column with coreference annotation (not yet implemented)",
    )

    parser.add_argument(
        "--drop_nested", action="store_true", help="drop information in nested column",
    )

    return parser.parse_args()


def read_xmi(xmi_file: str, xml_file: str, sanity_check: bool = True) -> ImpressoDocument:
    """Parse CAS/XMI document.

    :param str xmi_file: path to xmi_file.
    :param str xml_file: path to xml schema file.
    :param bool sanity_check: Perform annotation-independent sanity check.
    :return: A namedtuple with all the annotation information.
    :rtype: ImpressoDocument

    """

    neType = "webanno.custom.ImpressoNamedEntity"
    corefType = "webanno.custom.ImpressoCoreference"
    tokenType = "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Token"
    segmentType = "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence"
    imgLinkType = "webanno.custom.ImpressoImages"

    f_xmi = Path(xmi_file)
    filename = f_xmi.name
    filepath = str(f_xmi)
    docid = filename.split(".")[0]
    newspaper = docid.split("-")[0]
    date = "-".join(docid.split("-")[1:4])

    segments = OrderedDict()
    links = {}
    relations = []
    mentions = OrderedDict()

    with open(xml_file, "rb") as f:
        typesystem = load_typesystem(f)

    with open(xmi_file, "rb") as f:
        cas = load_cas_from_xmi(f, typesystem=typesystem)

    if sanity_check:
        check_entity_boundaries(cas.select(neType), tokenType, cas, filename)

    # read in the tokens
    for seg in cas.select(segmentType):
        tokens = []
        for tok in cas.select_covered(tokenType, seg):
            # ignore empty tokens
            if not tok.get_covered_text():
                continue
            try:
                token = {
                    "id": tok.xmiID,
                    "ann_layer": tok.type,
                    "start_offset": tok.begin,
                    "end_offset": tok.end,
                    "surface": tok.get_covered_text(),
                    "segment_id": seg.xmiID,
                }

                tokens.append(token)
            except Exception as e:
                msg = f"Problem with token annotation {tok.xmiID} in {xmi_file}"
                logging.error(msg)

        for img in cas.select_covered(imgLinkType, seg):
            try:
                iiif_link = img.link
                break
            except Exception as e:
                msg = f"Problem with IIIF-link annotation {img.xmiID} in {xmi_file}"
                logging.error(msg)
        else:
            msg = f"No IIIF-link annotation for segment {seg.xmiID} in {xmi_file}"
            logging.info(msg)
            iiif_link = "_"

        segment = {
            "segment_id": seg.xmiID,
            "start_offset": seg.begin,
            "end_offset": seg.end,
            "tokens": tokens,
            "iiif_link": iiif_link,
        }

        segments[seg.xmiID] = segment

    # read in the impresso entities
    for i, ent in enumerate(cas.select(neType)):
        try:
            entity = {
                "id": ent.xmiID,
                "id_cont": i,
                "ann_layer": ent.type,
                "entity_fine": ent.value,
                "entity_coarse": ent.value.split(".")[0],
                "entity_compound": ent.value.startswith("comp"),
                "start_offset": ent.begin,
                "end_offset": ent.end,
                "literal": ent.literal == "true",
                "surface": ent.get_covered_text().replace("\n", ""),
                "noisy_ocr": ent.noisy_ocr == "true",
                "transcript": ent.transcript,
            }

            if entity["entity_compound"] and entity["literal"]:
                msg = f"Entity compound {entity['surface']} is erroneously marked as literal in {xmi_file}."
                logging.error(msg)

            if entity["noisy_ocr"]:
                if entity["transcript"]:
                    entity["levenshtein_norm"] = compute_levenshtein_distance(
                        entity["surface"], entity["transcript"]
                    )
                else:
                    msg = f"Transcript for noisy entity {entity['surface']} is missing in {xmi_file}. Levenshtein distance cannot be computed and is set to 0."
                    logging.error(msg)
                    entity["levenshtein_norm"] = 0

            elif not entity["noisy_ocr"] and entity["transcript"]:
                msg = f"Transcript for entity {entity['surface']} is present in {xmi_file}, yet entity is not marked as noisy. Levenshtein distance is computed nevertheless."
                logging.error(msg)
                entity["levenshtein_norm"] = compute_levenshtein_distance(
                    entity["surface"], entity["transcript"]
                )

            else:
                entity["levenshtein_norm"] = 0

            mentions[ent.xmiID] = entity

            # read in the impresso links of named entity
            link = {
                "entity_id": ent.xmiID,
                "is_NIL": ent.is_NIL == "true",
                "wikidata_id": None,
            }
            try:
                link["wikidata_id"] = ent.wikidata_id
            except AttributeError:
                pass

            links[ent.xmiID] = link

        except Exception as e:
            msg = f"Problem with entity annotation {ent.xmiID} in {xmi_file}"
            logging.error(msg)

    document = ImpressoDocument(
        newspaper,
        date,
        docid,
        filename,
        filepath,
        segments,
        mentions,
        links,
        relations,
        cas.sofa_string,
    )

    return document


def convert_data(doc: ImpressoDocument, drop_nested: bool) -> [List]:
    """Select the relevant annotations per token for the finegrained format.

    :param ImpressoDocument doc: Document with all the annotation information.
    :param bool drop_nested: Drop annotation of nested entities and replace with underscore.
    :return: A nested list of tokens and its annotations.
    :rtype: [list]

    """

    rows = []

    # add meta header on the level of document
    rows += get_document_metadata(doc)

    for i_seg, seg in enumerate(doc.segments.values()):

        rows.append(["# segment_iiif_link = " + seg["iiif_link"]])

        for i_tok, tok in enumerate(seg["tokens"]):

            literals, non_literals, compounds = lookup_entity(tok, doc.mentions, doc)

            # only non-literal can be nested
            if drop_nested:
                fine_2 = "_"
            else:
                fine_2 = assemble_entity_label(non_literals, "entity_fine", nested=True)

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

            coarse_meto = assemble_entity_label(non_literals, "entity_coarse")
            coarse_lit = assemble_entity_label(literals, "entity_coarse")
            fine_meto = assemble_entity_label(non_literals, "entity_fine")
            fine_lit = assemble_entity_label(literals, "entity_fine")
            comp = assemble_entity_label(compounds, "entity_fine")

            # set longest entity span for literal and non-literal (metonymic)
            # to look up NEL
            main_ent_nonlit = non_literals[0][1] if non_literals else None
            main_ent_lit = literals[0][1] if literals else None

            nel_nonlit = lookup_nel(tok, main_ent_nonlit, doc)
            nel_lit = lookup_nel(tok, main_ent_lit, doc)

            misc = set_special_flags(tok, seg, main_ent_lit, main_ent_nonlit, doc)

            row = [
                tok["surface"],
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

    return rows


def get_document_metadata(doc: ImpressoDocument) -> [list]:
    """Set metadata on the level of segments (line).

    :param ImpressoDocument doc: Document with all the annotation information.
    :return: Nested list with various metadata
    :rtype: [list]

    """

    rows = []

    try:
        lang_dir = [part for part in Path(doc.filepath).parts if len(part) == 2][-1]
        lang = lang_dir.lower()
    except IndexError:
        lang = "LANG_ID"
        msg = f"Couldn't infer language from folder structure for file {doc.filepath}"
        logging.info(msg)

    rows.append(["# language = " + lang])
    rows.append(["# newspaper = " + doc.newspaper])
    rows.append(["# date = " + doc.date])
    rows.append(["# document_id = " + doc.id])

    return rows


def lookup_entity(tok: dict, mentions: dict, doc: ImpressoDocument) -> Tuple:
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

    compounds = [(iob, ent) for iob, ent in matches if ent["entity_compound"]]
    literals = [(iob, ent) for iob, ent in matches if ent["literal"]]
    non_literals = [
        (iob, ent) for iob, ent in matches if not ent["literal"] and not ent["entity_compound"]
    ]

    n_nested = (
        len(matches) - min(len(compounds), 1) - min(len(non_literals), 1) - min(len(literals), 1)
    )
    if len(non_literals) > 1:
        # allow one nesting
        n_nested = n_nested - 1

    # sanity checks
    if matches:
        ent_surface = matches[0][1]["surface"]
        if (literals or compounds) and not non_literals:
            msg = f"Token '{tok['surface']}' of entity '{ent_surface}' has no regular entity annotation (only compound or literal) in file {doc.filename}"
            logging.info(msg)
        if n_nested > 0:
            msg = f"Token '{tok['surface']}' of entity '{ent_surface}' has illegal entity overlappings (nesting) in file {doc.filename}"
            logging.info(msg)

    return literals, non_literals, compounds


def lookup_nel(
    token, entity, doc: ImpressoDocument, strip_base: bool = True, discard_time_links: bool = True
) -> str:
    """Get the link to wikidata entry of a named entity (NE).

    :param dict token: Annotation of the token.
    :param dict entity: Annotation of the main entity to look up the link.
    :param ImpressoDocument doc: Document with all the annotation information.
    :param bool strip_base: Keep only wikidata identifier instead of entire link.
    :param bool discard_time_links: Discard the wikidata link for time mentions even if present.
    :return: A Link to corresponding wikidata of the entity.
    :rtype: str

    """

    if entity:
        nel = doc.links[entity["id"]]

        # do sanity checks only once per named entity
        if entity["start_offset"] == token["start_offset"]:
            validate_link(nel, entity, doc)

        link = nel["wikidata_id"] if nel["wikidata_id"] else NIL_FLAG

        if discard_time_links and "time" in entity["entity_coarse"]:
            link = NIL_FLAG

        if strip_base:
            link = link.split("/")[-1]
    else:
        link = "_"

    return link


def lookup_coref(doc: ImpressoDocument, entity: dict, clusters: dict) -> str:
    """Get co-reference cluster of a named entity (NE).

    :param ImpressoDocument doc: Document with all the annotation information.
    :param dict entity: Annotation of entity.
    :param dict clusters: Collection of clusters
    :return: A coref identifier consisting of all IDs of NE (comma-separated)
    :rtype: str

    """

    if entity:
        for cluster in clusters:
            for member in cluster["members"]:
                if member["id"] == entity["id"]:
                    return cluster["cluster_id"]
        else:
            return f"{doc.id}|{entity['id']}"


def set_special_flags(
    tok: dict, seg: dict, ent_lit: dict, ent_meto: dict, doc: ImpressoDocument
) -> str:
    """Set a special flags if token is hyphenated or not followed by a whitespace.

    :param dict tok: Annotation of the token.
    :param dict seg: Annotation of the segment.
    :param dict ent_lit: Annotation of the literal entity.
    :param dict ent_meto: Annotation of the metonymic entity.
    :param ImpressoDocument doc: Document with all the annotation information.
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

        try:
            # sometimes the transcript is recorded for the metonymic entity instead of the literal one
            levenshtein_dist = max(ent_lit["levenshtein_norm"], ent_meto["levenshtein_norm"])
        except TypeError:
            levenshtein_dist = ent_lit["levenshtein_norm"]

        flags.append(f"{LEVENSHTEIN_FLAG}{levenshtein_dist:.2f}")

    if not flags:
        flags.append("_")

    # sort alphabetically, Levenshtein always last
    return "|".join(sorted(flags, key=lambda x: "Z" if "LED" in x else x))


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


def index_inception_files(dir_data, suffix=".xmi") -> list:
    """Index all .xmi files in the provided directory

    :param type dir_data: Path to top-level dir.
    :param type suffix: Only consider files of this type.
    :return: List of found files.
    :rtype: list

    """

    return sorted([path for path in Path(dir_data).rglob("*" + suffix)])


def find_coreference_clusters(doc: ImpressoDocument) -> List[set]:
    """Extract co-reference clusters from an annotated document.

    :param ImpressoDocument doc: Document with all the annotation information.
    :return: A list of co-reference clusters; each cluster is a set of entity
        IDs referering to entity mentions in `document.mentions`
    :rtype: List[set]

    """

    clusters = []

    try:
        assert doc.mentions
        assert doc.relations
    except AssertionError:
        msg = f"No coreference annotation in {doc.id}"
        logging.error(msg)

    for entity in doc.mentions:
        cluster = set()
        coreferents = find_coreferents(entity, doc)
        for eid in coreferents:
            other_coreferents = find_coreferents(eid, doc)
            for eid in other_coreferents:
                cluster.add(eid)
        if cluster and cluster not in clusters:
            clusters.append(cluster)

    return clusters


def find_coreferents(mention_id: int, doc: ImpressoDocument) -> set:
    """Find other mentions that refer to the same entity as the input mention.

    This is done by traversing the relation annotations with which
    we record entity co-reference information.

    :param int mention_id: ID of input entity mention.
    :param ImpressoDocument doc: Document with all the annotation information.
    :return: A set with IDs of co-referring mentions.
    :rtype: set

    """

    coreferents = set()

    for coref in doc.relations:
        if mention_id in coref["arguments"]:
            for arg in coref["arguments"]:
                coreferents.add(arg)
    return coreferents


def export_clusters(clusters: List[set], doc: ImpressoDocument) -> List[dict]:
    """Export a list of co-reference clusters.

    The unique ID of a coref cluster is assembled by all its named entity
    mentions which are comma-separated

    :param List[set] clusters: The list of annotated co-reference clusters.
    :param ImpressoDocument doc: Document with all the annotation information.
    :return: The list of clusters encoded in a pre-defined format.
    :rtype: List[dict]

    """

    export = []

    for n, cluster in enumerate(clusters):
        exported_cluster = {"id": n + 1, "members": []}

        ent_ids = sorted(cluster)
        cluster_id = ",".join([str(id) for id in ent_ids])
        exported_cluster["ent_ids"] = ent_ids
        exported_cluster["cluster_id"] = f"{doc.id}|{cluster_id}"

        for eid in ent_ids:
            mention = doc.mentions[eid]
            exported_cluster["members"].append(mention)
        export.append(exported_cluster)

    return export


def validate_link(
    nel: dict, entity: dict, doc: ImpressoDocument, labels: set = {"pers", "loc", "org", "prod"},
) -> bool:
    """
    Check whether there are missing or superfluous links for entities.

    :param dict nel: Annotation of the link.
    :param dict entity: Annotation of the entity.
    :param ImpressoDocument doc: Document with all the annotation information.
    :param set labels: Collection of labels that are supposed to have a link
    :return: False if there is accidentally no link, otherwise True.
    :rtype: bool
    """

    ent_surface = entity["surface"]

    if (
        not nel["wikidata_id"]
        and not nel["is_NIL"]
        and any(label in entity["entity_coarse"] for label in labels)
        and "unk" not in entity["entity_fine"]
    ):
        # entities are required to be linked unless they are NIL, UNK or mentions of time
        msg = f"Missing wikidata annotation for entity '{ent_surface}' in {doc.filename}"
        logging.info(msg)

        return False

    elif nel["wikidata_id"] and "time" in entity["entity_coarse"]:
        # mentions of time shouldn't be linked
        msg = f"Superfluous wikidata annotation for time mention '{ent_surface}' in {doc.filename}. It is set to NIL."
        logging.info(msg)

        return False
    else:
        return True


def check_coref_link_consistency(nel_gov, nel_child, ent_gov, ent_child) -> None:
    if nel_child["wikidata_id"] and nel_gov["wikidata_id"] != nel_child["wikidata_id"]:
        ent_gov_surface = ent_gov["surface"]
        ent_child_surface = ent_child["surface"]

        msg = f"Within co-ref chain, the parent entity '{ent_gov_surface}' has another wiki link than the child '{ent_child_surface}' in file"
        logging.info(msg)


def check_entity_boundaries(entities: Generator, tokenType: str, cas: Cas, fname: str) -> None:
    """
    Check whether the begin and the end of a named entities matches token boundaries.


    :param generator entities: All entities of the document.
    :param str tokenType: Type of tokens needed to lookup.
    :param str fname: Filename that is shown in log file.
    :param cas: Parsed Cassis document.
    :return: No return value.
    :rtype: None

    """

    for ent in entities:
        ent_tokens = list(cas.select_covered(tokenType, ent))

        if len(ent_tokens) < 1 or ent_tokens[0].begin != ent.begin or ent_tokens[-1].end != ent.end:
            ent_surface = ent.get_covered_text()
            ent_tok_surfaces = [tok.get_covered_text() for tok in ent_tokens]

            msg = f"Entity boundary of '{ent_surface}' doesn't match token boundary in {fname}. Full tokens covered: '{ent_tok_surfaces}'"
            logging.error(msg)


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
    msg = f"Start conversion of {len(xmi_files)} files."
    logging.info(msg)
    print(msg)

    for f_xmi, f_tsv in tqdm(list(zip(xmi_files, tsv_files))):

        info_msg = f"Converting {f_xmi} into {f_tsv}"
        logging.info(info_msg)

        doc = read_xmi(f_xmi, f_schema)
        f_tsv.parent.mkdir(parents=True, exist_ok=True)

        data = convert_data(doc, drop_nested)

        if coref:
            raise NotImplementedError("Coreference information is not yet implemented")
            clusters = export_clusters(find_coreference_clusters(doc), doc)
            # lookup_coref(doc, ent, clusters)

        with f_tsv.open("w") as tsvfile:
            writer = csv.writer(tsvfile, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar="")
            writer.writerow(COL_LABELS)
            writer.writerows(data)

    logging.info(f"Conversion completed.")


def main():

    args = parse_args()

    logging.basicConfig(
        filename=args.f_log,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    start_batch_conversion(args.dir_in, args.dir_out, args.f_schema, args.coref, args.drop_nested)


################################################################################
if __name__ == "__main__":
    main()
