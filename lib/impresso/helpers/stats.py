from tqdm import tqdm
import os
import logging
import pandas as pd
from typing import Tuple
from .inception import read_xmi_for_stats
from . import read_annotation_assignments

LOGGER = logging.getLogger(__name__)


def is_nested(row: pd.Series, mentions_df: pd.DataFrame) -> bool:
    start = row.start_offset
    end = row.end_offset

    if row.entity_coarse == "comp":
        return False

    containing_mentions = mentions_df[
        (start >= mentions_df.start_offset)
        & (end <= mentions_df.end_offset)
        & (mentions_df.doc_id == row.doc_id)
        & (mentions_df.entity_coarse != "comp")
        & (mentions_df.surface != row.surface)
    ][["start_offset", "end_offset", "surface", "doc_id", "entity_coarse"]]

    if containing_mentions.shape[0] > 0:
        LOGGER.info(f"Found nested entity {row.surface} {start} {end} {row.doc_id}")
        LOGGER.info(containing_mentions[["surface", "entity_coarse"]])

    return containing_mentions.shape[0] > 0


def read_split_assignments(input_dir: str) -> pd.DataFrame:
    languages = ["de", "en", "fr"]
    dfs = []
    for lang in languages:
        df = read_annotation_assignments(lang, input_dir)
        df["language"] = lang
        dfs.append(df)
    assignments_df = pd.concat(dfs)
    assignments_df = assignments_df[assignments_df["Document ID"].notnull()]
    assignments_df.set_index("Document ID", inplace=True, drop=False)
    assignments_df["Document ID"] = assignments_df["Document ID"].map(
        lambda id: id.replace(".txt", "").replace(".xmi", "")
    )
    return assignments_df[["Split"]]


def create_entity_dataframes(
    document_metadata_df: pd.DataFrame, nerc_only: bool = False
):

    mentions = []
    entities = []

    for doc_id, doc_metadata in tqdm(
        list(document_metadata_df.iterrows()),
        desc="Creating dataframes from annotated data (XMI)",
    ):

        # perhaps parallelize it with dask?
        doc_xmi_path = os.path.join(
            doc_metadata["base_dir"], doc_metadata["name"].replace(".txt", ".xmi")
        )
        doc_xml_path = os.path.join(doc_metadata["base_dir"], "TypeSystem.xml")
        doc = read_xmi_for_stats(doc_xmi_path, doc_xml_path)

        document_metadata_df.loc[doc_id, "n_tokens"] = len(doc.text.split())
        document_metadata_df.loc[doc_id, "n_mentions"] = len(doc.mentions)
        document_metadata_df.loc[doc_id, "n_entities"] = len(doc.links)

        for mention in list(doc.mentions.values()):
            mentions.append(
                {
                    "doc_id": doc_metadata["name"],
                    "annotation_id": mention["id"],
                    "entity_fine": mention["entity_fine"],
                    "entity_coarse": mention["entity_coarse"],
                    "surface": mention["surface"],
                    "is_literal": True if mention["literal"] else False,
                    "language": doc_metadata["language"],
                    "noisy_ocr": mention["noisy_ocr"],
                    "transcript": mention["transcript"],
                    "start_offset": mention["start_offset"],
                    "end_offset": mention["end_offset"],
                }
            )
        if not nerc_only:
            for entity in list(doc.links.values()):
                entities.append(
                    {
                        "doc_id": doc_metadata["name"],
                        "surface": entity["surface"],
                        "entity_id": entity["entity_id"],
                        "is_NIL": entity["is_NIL"],
                        "wikidata_id": entity["wikidata_id"],
                        "language": doc_metadata["language"],
                        "unsolvable_linking": entity["unsolvable_linking"],
                    }
                )
    mentions_df = pd.DataFrame(mentions)
    mentions_df["is_nested"] = mentions_df.apply(
        lambda row: is_nested(row, mentions_df), axis=1
    )
    entities_df = pd.DataFrame(entities)

    if nerc_only:
        return (document_metadata_df, mentions_df)
    else:
        return (document_metadata_df, mentions_df, entities_df)


def create_metadata_dataframes(data_dir: str) -> Tuple[pd.DataFrame, pd.DataFrame]:

    corpus_metadata = []
    document_metadata = []

    for lang in ["de", "fr", "en"]:

        base_dir = os.path.join(data_dir, lang)

        documents = [
            os.path.join(base_dir, file)
            for file in os.listdir(base_dir)
            if "xmi" in file
        ]

        for document in documents:

            document_name = os.path.basename(document)
            doc_canonical_id = document_name.replace(".txt", "").replace(".xmi", "")

            doc_metadata = {
                "doc_id": doc_canonical_id,
                "name": document_name,
                "path": document,
                "base_dir": base_dir,
                "newspaper": doc_canonical_id.split("-")[0],
                "year": int(doc_canonical_id.split("-")[1]),
                "language": lang,
                "n_tokens": None,
                "n_mentions": None,
                "n_relations": None,
                "n_entities": None,
            }
            document_metadata.append(doc_metadata)

        metadata = {
            "n_documents": len(documents),
            "n_annotated_documents": len(documents),
            "language": lang,
            "path": base_dir,
        }

        corpus_metadata.append(metadata)

    return (
        pd.DataFrame(corpus_metadata).set_index("language", drop=False),
        pd.DataFrame(document_metadata).set_index("doc_id"),
    )
