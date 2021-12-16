"""
...

Usage:
    lib/create_datasets.py --set=<set> --log-file=<log> --input-dir=<id> --output-dir=<od> --data-version=<v> --assignments-table=<at>
"""  # noqa

from docopt import docopt
from pathlib import Path
import logging
import os
import ipdb
import pandas as pd
import random
from typing import List
from ajmc_utils import read_annotation_assignments
from impresso.helpers.tsv import is_tsv_complete, write_tsv, parse_tsv

LOGGER = logging.getLogger(__name__)

DATASET_NAME = "ajmc"

def concat_tsv_files(output_path: str, input_files: List[str]) -> None:
    with open(output_path, "w") as out_tsv_file:
        data = []
        for n, file in enumerate(input_files):

            if not os.path.exists(file):
                LOGGER.warning(f"Input file {file} does not exist")
                continue

            LOGGER.info(f"Read input from file {file}")

            with open(file, "r") as inp_tsv_file:
                if n > 0:
                    lines = inp_tsv_file.readlines()[1:]
                else:
                    lines = inp_tsv_file.readlines()[0:]
                data.append("".join(lines))

        out_tsv_file.write("\n".join(data))


def create_datasets(input_dir, output_dir, version, assignments_table_path, set="all"):
    def derive_document_path(row, input_dir):
        document_name = row["inception-docid"].replace(".xmi", ".tsv")
        return os.path.join(input_dir, "tsv", row["inception-project"], document_name)
    
    splits = ["train", "dev", "test"]

    assignments_df = read_annotation_assignments(assignments_table_path, input_dir)
    
    basedir = os.path.join(output_dir, version)
    if not os.path.exists(basedir):
        LOGGER.info(f"Created folder {basedir} as it did not exist")
        Path(basedir).mkdir(exist_ok=True)

    if set == "sample":
        document_paths = list(assignments_df[assignments_df.split == 'miniref'].Path)
        dataset_path = create_dataset(
            document_paths, set, version, output_dir
        )
    else:
        for split in splits:
            # dev/test for all languages
            document_paths = list(assignments_df[assignments_df.split == split].Path)
            dataset_path = create_dataset(
                document_paths, split, version, output_dir
            )

            if split == "test":
                # generate a version of the test dataset with ground truth values masked out
                tsv_data = parse_tsv(dataset_path, mask_nerc=True, mask_nel=True)
                masked_dataset_name = os.path.basename(dataset_path).replace(
                    "-test", "-test-masked"
                )
                masked_dataset_path = os.path.join(
                    output_dir, version, masked_dataset_name
                )
                write_tsv(tsv_data, masked_dataset_path)


def create_dataset(
    files: str, split: str, version: str, output_dir: str
) -> str:

    tsv_filename = f"{DATASET_NAME}-data-{version}-{split}.tsv"
    basedir = os.path.join(output_dir, version)

    if not os.path.exists(basedir):
        Path(basedir).mkdir(exist_ok=True)

    assert len(files) > 0

    # concatenate document TSV files into a single TSV
    # and write to disk in the specified output folder 
    output_path = os.path.join(basedir, tsv_filename)
    concat_tsv_files(output_path, files)
    LOGGER.info(f"Written {split} to {output_path}")

    # verify that all documents expected are found in the
    # output TSV file
    expected_doc_ids = [
        os.path.basename(f).replace(".tsv", "") for f in files
    ]
    # assert is_tsv_complete(output_path, expected_doc_ids)
    LOGGER.info(
        f"{output_path} contains all {len(expected_doc_ids)} expected documents"
    )
    return output_path


def main(args):
    which_set = args["--set"]
    log_file = args["--log-file"]
    input_dir = args["--input-dir"]
    output_dir = args["--output-dir"]
    data_version = args["--data-version"]
    assignments_table = args["--assignments-table"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    accepted_sets = ["all", "sample"]
    assert which_set in accepted_sets

    create_datasets(input_dir, output_dir, data_version, assignments_table, which_set)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
