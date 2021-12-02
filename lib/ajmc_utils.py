"""Various helpers."""

__author__ = "Matteo Romanello"
__email__ = "matteo.romanello@unil.ch"
__organisation__ = "UNIL, ASA"
__status__ = "development"

import pdb
import os
import logging
import csv
from pathlib import Path
from collections import OrderedDict
from tqdm import tqdm
from impresso.helpers import compute_levenshtein_distance
from typing import NamedTuple
from cassis import Cas, load_cas_from_xmi, load_typesystem

BIBLIO_ENTITIES = [
    "primary-full",
    "primary-partial",
    "secondary-full",
    "secondary-partial",
    "secondary-meta"
]

AjmcDocument = NamedTuple(
    "AjmcDocument",
    [
        ("id", str),
        ("filename", str),
        ("filepath", str),
        ("sentences", dict),
        ("mentions", dict),
        ("links", list),
        ("text", str),
    ],
)


def read_xmi(xmi_file: str, xml_file: str, sanity_check: bool = True) -> AjmcDocument:
    """Parse CAS/XMI document.

    :param str xmi_file: path to xmi_file.
    :param str xml_file: path to xml schema file.
    :param bool sanity_check: Perform annotation-independent sanity check.
    :return: A namedtuple with all the annotation information.
    :rtype: AjmcDocument

    """

    neType = "webanno.custom.AjMCNamedEntity"
    segmentType = 'de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence'
    sentenceType = 'webanno.custom.GoldSentences'
    hyphenationType = 'webanno.custom.GoldHyphenation'
    tokenType = "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Token"

    f_xmi = Path(xmi_file)
    filename = f_xmi.name
    filepath = str(f_xmi)
    docid = filename.split(".")[0]

    segments = OrderedDict()
    links = {}
    mentions = OrderedDict()

    with open(xml_file, "rb") as f:
        typesystem = load_typesystem(f)

    with open(xmi_file, "rb") as f:
        cas = load_cas_from_xmi(f, typesystem=typesystem)

    #if sanity_check:
    #    check_entity_boundaries(cas.select(neType), tokenType, cas, filename)

    # read in the tokens from golden sentences
    for seg in cas.select(sentenceType):
        tokens = []
        for tok in cas.select_covered(tokenType, seg):
            # ignore empty tokens
            if not tok.get_covered_text():
                continue
            try:
                token = {
                    "id": tok.xmiID,
                    "ann_layer": tokenType,
                    "start_offset": tok.begin,
                    "end_offset": tok.end,
                    "surface": tok.get_covered_text(),
                    "segment_id": seg.xmiID,
                }

                tokens.append(token)
            except Exception as e:
                msg = f"Problem with token annotation {tok.xmiID} in {xmi_file}"
                logging.error(msg)

        segment = {
            "segment_id": seg.xmiID,
            "start_offset": seg.begin,
            "end_offset": seg.end,
            "tokens": tokens,
            "corrupted": seg.corrupted,
            "incomplete_continuing": seg.incomplete_continuing,
            "incomplete_truncated": seg.incomplete_truncated
        }

        segments[seg.xmiID] = segment

    # read in the named entities
    for i, ent in enumerate(cas.select(neType)):
        try:
            assert ent.value is not None

            entity = {
                "id": ent.xmiID,
                "id_cont": i,
                "ann_layer": neType,
                "entity_fine": ent.value,
                "entity_coarse": ent.value.split(".")[0] if "." in ent.value else ent.value,
                "entity_biblio": ent.value if ent.value in BIBLIO_ENTITIES else None,
                "start_offset": ent.begin,
                "end_offset": ent.end,
                "literal": "true", # we don't have metonymy, so...
                "surface": ent.get_covered_text().replace("\n", ""),
                "noisy_ocr": ent.noisy_ocr,
                "transcript": ent.transcript,
            }

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

            links[ent.xmiID] = link

        except Exception as e:
            msg = f"Problem with entity annotation {ent.xmiID} in {xmi_file}"
            logging.error(e)
            logging.error(msg)
            #raise e
            #pdb.set_trace()

    document = AjmcDocument(
        docid,
        filename,
        filepath,
        segments,
        mentions,
        links,
        cas.sofa_string,
    )

    return document