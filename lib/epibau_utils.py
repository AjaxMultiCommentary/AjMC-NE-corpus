"""Various helpers."""

__author__ = "Matteo Romanello"
__email__ = "matteo.romanello@unil.ch"
__organisation__ = "UNIL, ASA"
__status__ = "development"


import os
import logging
import csv
from pathlib import Path
from collections import OrderedDict
from tqdm import tqdm
from typing import NamedTuple
from cassis import Cas, load_cas_from_xmi, load_typesystem

EpibauDocument = NamedTuple(
    "EpibauDocument",
    [
        ("id", str),
        ("filename", str),
        ("filepath", str),
        ("segments", dict),
        ("mentions", dict),
        ("links", list),
        ("relations", list),
        ("text", str),
    ],
)


def read_xmi(xmi_file: str, xml_file: str, sanity_check: bool = True) -> EpibauDocument:
    """Parse CAS/XMI document.

    :param str xmi_file: path to xmi_file.
    :param str xml_file: path to xml schema file.
    :param bool sanity_check: Perform annotation-independent sanity check.
    :return: A namedtuple with all the annotation information.
    :rtype: EpibauDocument

    """

    neType = "webanno.custom.CitationComponents"
    reType = "webanno.custom.Re"
    posType = 'de.tudarmstadt.ukp.dkpro.core.api.lexmorph.type.pos.POS'
    segmentType = 'de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Sentence'
    tokenType = "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Token"

    f_xmi = Path(xmi_file)
    filename = f_xmi.name
    filepath = str(f_xmi)
    docid = filename.split(".")[0]

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

        segment = {
            "segment_id": seg.xmiID,
            "start_offset": seg.begin,
            "end_offset": seg.end,
            "tokens": tokens,
        }

        segments[seg.xmiID] = segment

    # read in the impresso entities
    for i, ent in enumerate(cas.select(neType)):
        try:
            entity = {
                "id": ent.xmiID,
                "id_cont": i,
                "ann_layer": ent.type,
                "entity_fine": None,
                "entity_coarse": ent.value,
                "entity_compound": None,
                "start_offset": ent.begin,
                "end_offset": ent.end,
                "literal": "true", # we don't have metonymy, so...
                "surface": ent.get_covered_text().replace("\n", ""),
                #"noisy_ocr": ent.noisy_ocr == "true" if "noisy_ocr" in ent else None,
                #"transcript": ent.transcript if "transcript" in ent else None,
            }
            """
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
            """

            mentions[ent.xmiID] = entity

            # read in the impresso links of named entity
            link = {
                "entity_id": ent.xmiID,
                #"is_NIL": ent.is_NIL == "true",
                "wikidata_id": None,
            }
            try:
                link["wikidata_id"] = ent.wikidata_id
            except AttributeError:
                pass

            try:
                entity['author_uri'] = ent.author_uri
            except AttributeError:
                pass

            try:
                entity['work_uri'] = ent.work_uri
            except AttributeError:
                pass

            try:
                entity['norm_scope'] = ent.norm_scope
            except AttributeError:
                pass

            links[ent.xmiID] = link

        except Exception as e:
            msg = f"Problem with entity annotation {ent.xmiID} in {xmi_file}"
            logging.error(msg)
            raise e

    document = EpibauDocument(
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