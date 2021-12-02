"""
...

Usage:
    lib/inject_iiif_links.py --input-dir=<id> --temp-dir=<od> --schema=<sf> --log-file=<log>
"""  # noqa

import ipdb
import pandas as pd
from docopt import docopt
from pathlib import Path
import logging
import os
import random
from typing import List
from tqdm import tqdm
from helpers import read_annotation_assignments
from helpers.xmi import find_xmi_files, contains_iiif_links, copy_iiif_links
from prepare import serialize2xmi, select_data
from impresso_commons.path import parse_canonical_filename

LOGGER = logging.getLogger(__name__)

S3_REBUILT_BUCKET = "s3://canonical-rebuilt-release"
S3_CANONICAL_BUCKET = "s3://original-canonical-release"


def group_content_items(content_items: List[str]):
    """Groups content items by year and then by newspaper."""
    cis_by_year = {}
    for ci in content_items:
        np, date, edition, ci_type, id, ext = parse_canonical_filename(ci)
        year = date[0]

        if year not in cis_by_year:
            cis_by_year[year] = {}

        if np not in cis_by_year[year]:
            cis_by_year[year][np] = []

        cis_by_year[year][np].append(ci)
    return cis_by_year


def run_inject_links(input_dir: str, xmi_schema: str, temp_dir: str) -> None:

    xmi_files = find_xmi_files(input_dir)

    xmis_iiif_situation = [
        (
            contains_iiif_links(file, xmi_schema),
            os.path.basename(file).replace(".xmi", "").replace(".txt", ""),
        )
        for file in tqdm(xmi_files, desc="Checking for missing IIIF links.")
        if "NZZ" not in file
    ]

    missing_iiif_links = [
        {"ci_id": doc_id} for has_links, doc_id in xmis_iiif_situation if not has_links
    ]

    df = pd.DataFrame(missing_iiif_links)
    print(f"There are {df.shape[0]} content items with missing IIIF links")

    content_items = select_data(df, S3_REBUILT_BUCKET)
    print(f"Retrieved {len(content_items)} content items from {S3_REBUILT_BUCKET}")

    xmi_files_with_links = serialize2xmi(
        contentitems=content_items,
        xmi_schema=xmi_schema,
        canonical_bucket=S3_CANONICAL_BUCKET,
        output_dir=temp_dir,
        pct_coordinates=False,
    )

    for doc_id in tqdm(
        list(df.ci_id),
        desc=f"Copying IIIF links onto the annotated documents in {input_dir}",
    ):
        annotated_xmi = [f for f in xmi_files if doc_id in f][0]
        rebuilt_xmi = os.path.join(temp_dir, f"{doc_id}.xmi")
        LOGGER.info(f'Copying {rebuilt_xmi} to {annotated_xmi}')
        copy_iiif_links(rebuilt_xmi, annotated_xmi, xmi_schema)


def main(args):
    log_file = args["--log-file"]
    input_dir = args["--input-dir"]
    temp_dir = args["--temp-dir"]
    schema_path = args["--schema"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    run_inject_links(input_dir, schema_path, temp_dir)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
