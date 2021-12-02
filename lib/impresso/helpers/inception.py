import argparse
import io
import logging
import os
import sys
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Generator, List, Tuple

from cassis import Cas, load_cas_from_xmi, load_typesystem
from pycaprio import Pycaprio
from pycaprio.core.objects.project import Project
from pycaprio.mappings import InceptionFormat

from . import ImpressoDocument

LOGGER = logging.getLogger(__name__)


def find_project_by_name(inception_client: Pycaprio, project_name: str) -> Project:
    """Finds a project in INCEpTION by its name.

    :param Pycaprio inception_client: Pycaprio INCEpTION client.
    :param str project_name: project name.
    :return: Description of returned object.
    :rtype: type

    """
    matching_projects = [project for project in inception_client.api.projects() if project.project_name == project_name]
    assert len(matching_projects) == 1
    return matching_projects[0]


def make_inception_client():
    """Creates a Pycaprio client to INCEpTION.

    Connection parameters are read from environment variables.
    """
    LOGGER.info(
        (
            'Using following INCEpTION connection parameters (from environment): '
            f"Host: {os.environ['INCEPTION_HOST']}; user: {os.environ['INCEPTION_USERNAME']}; "
            f"password: {'set (hidden for security)' if 'INCEPTION_PASSWORD' in os.environ else 'not set'}"
        )
    )
    return Pycaprio()


def index_project_documents(project_id: int, inception_client: Pycaprio) -> Tuple[dict, dict]:
    """Creates two inverted indexes of documents in a project in INCEpTION.

    :param int project_id: Description of parameter `project_id`.
    :param Pycaprio inception_client: Description of parameter `inception_client`.
    :return: Description of returned object.
    :rtype: Tuple[dict, dict]

    """
    id2name_idx = {}
    name2id_idx = {}
    documents = inception_client.api.documents(project_id)
    for document in documents:
        id2name_idx[document.document_id] = document.document_name
        name2id_idx[document.document_name] = document.document_id
    return (id2name_idx, name2id_idx)


def download_document(
    project_id: int, document_id: int, user: str, output_dir: str, inception_client: Pycaprio
) -> None:
    """Downloads an annotated document (by ID) from INCEpTION as unzipped UIMA/XMI."""

    annotated_doc = inception_client.api.annotation(
        project_id, document_id, user, annotation_format=InceptionFormat.XMI
    )

    xmi_document = zipfile.ZipFile(io.BytesIO(annotated_doc))
    xmi_document.extractall(output_dir)
    LOGGER.info(f'Downloaded annotations from user {user} for {document_id} from project {project_id}')


# this is Alex's function but slightly tweaked for the needs of stats
def read_xmi_for_stats(xmi_file: str, xml_file: str) -> ImpressoDocument:
    """Parse CAS/XMI document.

    :param str xmi_file: path to xmi_file.
    :param str xml_file: path to xml schema file.
    :param bool sanity_check: Perform annotation-independent sanity check.
    :return: A namedtuple with all the annotation information.
    :rtype: ImpressoDocument

    """

    neType = "webanno.custom.ImpressoNamedEntity"
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
    iiifs = []

    with open(xml_file, "rb") as f:
        typesystem = load_typesystem(f)

    with open(xmi_file, "rb") as f:
        cas = load_cas_from_xmi(f, typesystem=typesystem)

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
            "iiif_link": "",
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
                "entity_coarse": ent.value.split(".")[0] if ent.value else None,
                "entity_compound": ent.value.startswith("comp") if ent.value else None,
                "start_offset": ent.begin,
                "end_offset": ent.end,
                "literal": ent.literal == "true",
                "surface": ent.get_covered_text().replace('\n', ''),
                "noisy_ocr": ent.noisy_ocr,
                "transcript": ent.transcript,
            }

            mentions[ent.xmiID] = entity

            # read in the impresso links of named entity
            link = {
                "surface": entity['surface'],
                "entity_id": ent.xmiID,
                "is_NIL": ent.is_NIL == "true",
                "wikidata_id": None,
                "unsolvable_linking": ent.unsolvable_linking == 'true',
            }
            try:
                link["wikidata_id"] = ent.wikidata_id
            except AttributeError:
                pass

            links[ent.xmiID] = link

        except Exception as e:
            msg = f"Problem with entity annotation {ent.xmiID} in {xmi_file}"
            print(e)
            logging.error(msg)

    document = ImpressoDocument(
        newspaper, date, docid, filename, filepath, segments, mentions, links, relations, cas.sofa_string,
    )

    return document
