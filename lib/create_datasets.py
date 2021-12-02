"""
...

Usage:
    lib/create_datasets.py --log-file=<log> --input-dir=<id> --output-dir=<od> --data-version=<v>
"""  # noqa

from docopt import docopt
from pathlib import Path
import logging
import os
import pandas as pd
import random
from typing import List
from impresso.helpers.tsv import is_tsv_complete, write_tsv, parse_tsv

LOGGER = logging.getLogger(__name__)

DATASET_NAME = "EpiBau"

def read_annotation_assignments(filename: str, input_dir: str) -> pd.DataFrame:
    """Reads a CSV export of annotation assignment spreadsheet into a DataFrame.

    :param str corpus: Description of parameter `corpus`.
    :param str input_dir: Description of parameter `input_dir`.
    :return: A pandas DataFrame
    :rtype: pd.DataFrame

    """
    assignments_csv_path = (
        f"{os.path.join(input_dir, filename)}"
    )
    assert os.path.exists(assignments_csv_path)
    return pd.read_csv(assignments_csv_path, sep='\t', encoding="utf-8")

def concat_tsv_files(output_path: str, input_files: List[str]) -> None:
    with open(output_path, "w") as out_tsv_file:
        data = []
        for n, file in enumerate(input_files):

            if not os.path.exists(file):
                LOGGER.warning(f"Input file {file} does not exist")
                continue

            LOGGER.debug(f"Read input from file {file}")

            with open(file, "r") as inp_tsv_file:
                if n > 0:
                    lines = inp_tsv_file.readlines()[1:]
                else:
                    lines = inp_tsv_file.readlines()[0:]
                data.append("".join(lines))

        out_tsv_file.write("\n".join(data))


def create_datasets(input_dir, output_dir, version):
    def derive_document_path(row, input_dir):
        document_name = row["inception-docid"].replace(".xmi", ".tsv")
        return os.path.join(input_dir, "tsv", row["inception-project"], document_name)

    splits = ["train", "dev", "test"]
    basedir = os.path.join(output_dir, version)

    if not os.path.exists(basedir):
        LOGGER.info(f"Created folder {basedir} as it did not exist")
        Path(basedir).mkdir(exist_ok=True)

    assignments_df = read_annotation_assignments("epibau-corpus-metadata.tsv", input_dir)
    assignments_df.dropna(subset=['inception-project'], inplace=True)
    # add path of each document in the dataframe
    # if it's marked as isMiniRef, then it's different
    assignments_df["Path"] = assignments_df.apply(
        lambda row: derive_document_path(row, input_dir), axis=1
    )

    for split in splits:

        # dev/test for all languages
        document_paths = list(assignments_df[assignments_df.split == split].Path)
        dataset_path = create_dataset(
            document_paths, split, version, output_dir
        )

        # verify that all documents are found in the TSV file
        expected_doc_ids = [
            os.path.basename(f).replace(".tsv", "") for f in document_paths
        ]
        assert is_tsv_complete(dataset_path, expected_doc_ids)
        LOGGER.info(
            f"{dataset_path} contains all {len(expected_doc_ids)} expected documents"
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

    output_path = os.path.join(basedir, tsv_filename)
    concat_tsv_files(output_path, files)
    LOGGER.info(f"Written {split} to {output_path}")
    return output_path


def main(args):
    log_file = args["--log-file"]
    input_dir = args["--input-dir"]
    output_dir = args["--output-dir"]
    data_version = args["--data-version"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    create_datasets(input_dir, output_dir, data_version)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
