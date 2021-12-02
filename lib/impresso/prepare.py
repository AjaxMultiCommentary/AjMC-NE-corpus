"""
Script to fetch sampled newspaper content items from s3 and convert them into
UIMA/XMI format for annotation in INCEpTION. Sampling data is read from a .tsv
export of our shared spreadsheets (one per newspaper).

Usage:
    lib/prepare.py --corpus=<c> --input-file=<if> --schema=<sf> --output-dir=<od> --canonical-bucket=<cb> --rebuilt-bucket=<rb> --log-file=<log>
"""  # noqa

from __future__ import print_function
from docopt import docopt
from typing import List
import argparse
import pickle
import pkg_resources
import os
import os.path
import json
import pathlib
from random import shuffle
import pandas as pd
import logging
from dask.distributed import Client
from dask import bag as db
from impresso_commons.path import parse_canonical_filename
from impresso_commons.utils import init_logger
from impresso_commons.utils.uima import get_iiif_links
from impresso_commons.utils.s3 import IMPRESSO_STORAGEOPT
from impresso_commons.classes import ContentItem, ContentItemCase
from impresso_commons.utils.uima import rebuilt2xmi
from tqdm import tqdm


def group_content_items(df):
    """Group by year and then by newspaper."""
    cis_by_year = {}
    for ci in df.to_dict(orient="records"):
        np, date, edition, ci_type, id, ext = parse_canonical_filename(ci["ci_id"])
        year = date[0]

        if year not in cis_by_year:
            cis_by_year[year] = {}

        if np not in cis_by_year[year]:
            cis_by_year[year][np] = []

        cis_by_year[year][np].append(ci)
    return cis_by_year


def read_tsv(filepath):
    temp_df = pd.read_csv(filepath, sep="\t", error_bad_lines=False)
    new_col_names = {col: col.lower().replace("-", "_") for col in temp_df.columns}
    temp_df.rename(mapper=new_col_names, axis="columns", inplace=True)
    return temp_df


def read_data(input_dir):
    """Reads CSV files (from triage) and returns a dataframe"""
    dfs = []
    for file in os.listdir(input_dir):
        if ".skip" in file:
            continue
        temp_df = read_tsv(os.path.join(input_dir, file))
        dfs.append(temp_df)

    return pd.concat(dfs, sort=False)


def fetch_content_items(np, year, ci_ids, bucket):
    """Fetch content items in JSON from s3."""
    filename = f"{bucket}/{np}/{np}-{year}.jsonl.bz2"
    content_items = (
        db.read_text(filename, storage_options=IMPRESSO_STORAGEOPT)
        .map(lambda item: json.loads(item))
        .filter(lambda item: item["id"] in ci_ids)
        .compute()
    )
    logging.info(f"{np}-{year}: fecthed {len(content_items)} items")
    return content_items


def select_data(selection_df: pd.DataFrame, rebuilt_bucket: str) -> List[ContentItem]:
    """Fetches from S3 the content items selected during triage.

    :param pd.DataFrame selection_df: Description of parameter `selection_df`.
    :param str rebuilt_bucket: S3 bucket with rebuilt data.
    :return: A list of ContentItem instances.
    :rtype: List[ContentItem]

    """
    # group content items by year, since in s3 they are packaged by year
    cis_by_year = group_content_items(selection_df)
    selected_content_items = []

    print(f"\nReading data from {rebuilt_bucket}")
    for year in tqdm(cis_by_year.keys(), desc="Reading rebuilt data from S3"):

        for np in cis_by_year[year]:

            ci_ids = [ci["ci_id"] for ci in cis_by_year[year][np]]
            selected_content_items += fetch_content_items(
                np, year, ci_ids, rebuilt_bucket
            )

    return [
        ContentItem.from_json(data=ci, case=ContentItemCase.FULL)
        for ci in selected_content_items
    ]


def write_manifest(contentitem_ids: List[str], manifest_path: str) -> None:
    """Writes a list of content items IDs to a MANIFEST file.

    :param List[str] contentitem_ids: Description of parameter `contentitem_ids`.
    :param str manifest_path: Path to the MANIFEST file.
    :return: Does not return anything.
    :rtype: None

    """

    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            existing_contentitems = f.read().split("\n")
    else:
        existing_contentitems = []

    with open(manifest_path, "w") as f:
        # make sure we don't add duplicates
        f.write("\n".join(set(existing_contentitems + contentitem_ids)))
    print(f"\nAdded {len(contentitem_ids)} IDs to MANIFEST {manifest_path}")


def serialize2json(contentitems: List[ContentItem], output_dir: str) -> None:
    """Serializes a list of ContentItems as JSON files.

    :param List[ContentItem] contentitems: ContentItems to serialize.
    :param str output_dir: Output directory path.
    :return: Description of returned object.
    :rtype: None

    """
    print("\nSerializing JSON files to {output_dir}")
    for content_item in tqdm(contentitems):

        # create `json` subfolder if it does not exist
        try:
            pathlib.Path(output_dir).mkdir(parents=True)
        except Exception:
            pass

        # serialize to JSON format
        content_item.to_json(output_dir, case=ContentItemCase.FULL)
        logging.info(
            f"Written item {content_item.id} to {os.path.join(output_dir, content_item.id)}.json"
        )
    return


def serialize2xmi(
    contentitems: List[ContentItem],
    xmi_schema: str,
    canonical_bucket: str,
    output_dir: str,
    pct_coordinates: bool = False,
) -> List[str]:
    """Serializes a list of ContentItems as XMI files.

    :param List[ContentItem] contentitems: contentitems: ContentItems to serialize.
    :param str xmi_schema: XMI schema of annotations (TypeSystem.xml).
    :param str canonical_bucket: S3 bucket with input canonical data.
    :param str output_dir: Output directory path.
    :param bool pct_coordinates: Flag indicating whether coordinates are expressed as percentages.
    :return: List of serialized XMI files.
    :rtype: List[str]

    """

    output_files = []
    iiif_mappings = get_iiif_links(contentitems, canonical_bucket)

    print(f"\nSerializing XMI files to {output_dir}")

    for contentitem in tqdm(contentitems):
        xmi_file = rebuilt2xmi(
            contentitem, output_dir, xmi_schema, iiif_mappings, pct_coordinates
        )
        logging.info(f"Written item {contentitem.id} to {xmi_file}")
        output_files.append(xmi_file)

    return output_files


def run_prepare_data(
    triage_file_path: str,
    corpus: str,
    xmi_schema: str,
    canonical_bucket: str,
    rebuilt_bucket: str,
    output_dir: str,
):
    """Runs the various steps of data preparation.

    These steps are:
    1. determining data to select based on triage file (.tsv)
    2. serializing selected items as JSON files (for traceability/debug)
    3. transforming and serializing the JSON items as UIMA/XMI files
    4. updating the corresponding MANIFEST file (one per corpus)

    :param str triage_file_path: Path to the triage .tsv file.
    :param str corpus: Corpus identifier (e.g. "en", "fr", etc.).
    :param str xmi_schema: Description of parameter `xmi_schema`.
    :param str canonical_bucket: Description of parameter `canonical_bucket`.
    :param str rebuilt_bucket: Description of parameter `rebuilt_bucket`.
    :param str output_dir: Description of parameter `output_dir`.
    :return: Description of returned object.
    :rtype: type

    """

    df = read_tsv(triage_file_path)
    selection = df[(df.article_selected == True)]
    logging.info(
        f"Triage file {triage_file_path} contains {selection.shape[0]} selected content items"
    )
    selected_content_items = select_data(selection, rebuilt_bucket)

    # destinations of serialized data
    json_dir = os.path.join(output_dir, corpus, "json")
    xmi_dir = os.path.join(output_dir, corpus, "xmi")

    serialize2json(selected_content_items, json_dir)
    percentage_coordinates = True if corpus == "en" else False
    serialize2xmi(
        selected_content_items,
        xmi_schema,
        canonical_bucket,
        xmi_dir,
        percentage_coordinates,
    )

    # add the IDs of the new content items just prepared to the MANIFEST.txt file
    ci_ids = [item.id for item in selected_content_items]
    manifest_file = os.path.join(output_dir, f"MANIFEST-{corpus}.txt")
    write_manifest(ci_ids, manifest_file)


def main(args):

    triag_file = args["--input-file"]
    log_file = args["--log-file"]
    output_dir = args["--output-dir"]
    s3_canonical_bucket = args["--canonical-bucket"]
    s3_rebuilt_bucket = args["--rebuilt-bucket"]
    xmi_schema = args["--schema"]
    corpus = args["--corpus"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    run_prepare_data(
        triag_file,
        corpus,
        xmi_schema,
        s3_canonical_bucket,
        s3_rebuilt_bucket,
        output_dir,
    )


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
