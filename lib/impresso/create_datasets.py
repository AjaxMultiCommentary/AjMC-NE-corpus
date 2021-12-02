"""
...

Usage:
    lib/create_datasets.py --set=<set> --log-file=<log> --input-dir=<id> --output-dir=<od> --data-version=<v>
"""  # noqa

import ipdb
from docopt import docopt
from pathlib import Path
import logging
import os
import random
from typing import List
from helpers import read_annotation_assignments
from helpers.tsv import is_tsv_complete, write_tsv, parse_tsv

LOGGER = logging.getLogger(__name__)


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


def create_sample(input_dir, output_dir, version):

    langs = ["fr", "de"]

    for lang in langs:
        corpus_input_dir = os.path.join(input_dir, lang, "tsv")
        output_path = os.path.join(
            output_dir, version, lang, f"HIPE-data-{version}-sample-{lang}.tsv"
        )
        logging.info(output_path)

        files = [
            os.path.join(corpus_input_dir, file)
            for file in os.listdir(corpus_input_dir)
        ]
        logging.info(f"Found {len(files)} .tsv files in {corpus_input_dir}")

        with open(output_path, "w") as out_tsv_file:
            data = []
            for n, file in enumerate(files):
                with open(file, "r") as inp_tsv_file:
                    if n > 0:
                        lines = inp_tsv_file.readlines()[1:]
                    else:
                        lines = inp_tsv_file.readlines()[0:]
                    data.append("".join(lines))

            out_tsv_file.write("\n".join(data))


def create_datasets(input_dir, output_dir, version):
    def derive_document_path(row, input_dir, lang):
        if row["Document ID"]:
            if row["Document ID"] is None:
                return None
            if ".xmi" in row["Document ID"]:
                document_name = row["Document ID"].replace(".xmi", ".tsv")
            elif ".txt" in row["Document ID"]:
                document_name = row["Document ID"].replace(".txt", ".tsv")
            annotation_dir = "annotated_retok"

            return os.path.join(input_dir, annotation_dir, lang, "tsv", document_name)
        else:
            return None

    langs = ["en", "fr", "de"]
    splits = ["train", "dev", "test"]
    basedir = os.path.join(output_dir, version)

    if not os.path.exists(basedir):
        LOGGER.info(f"Created folder {basedir} as it did not exist")
        Path(basedir).mkdir(exist_ok=True)

    for lang in langs:

        assignments_df = read_annotation_assignments(lang, input_dir)
        assignments_df = assignments_df[
            (assignments_df["Document ID"].notnull())
            & (assignments_df["NERC assignee"].notnull())
            & (assignments_df["NERC status"] == "done")
            & (assignments_df["NEL status"] == "done")
        ]
        import ipdb; ipdb.set_trace()
        # add path of each document in the dataframe
        # if it's marked as isMiniRef, then it's different
        assignments_df["Path"] = assignments_df.apply(
            lambda row: derive_document_path(row, input_dir, lang), axis=1
        )

        for split in splits:
            # no training data for English
            if lang == "en" and split == "train":
                continue

            # dev/test for all languages
            document_paths = list(assignments_df[assignments_df.Split == split].Path)
            dataset_path = create_dataset(
                document_paths, lang, split, version, output_dir
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
                    "-test-", "-test-masked-"
                )
                masked_dataset_path = os.path.join(
                    output_dir, version, lang, masked_dataset_name
                )
                write_tsv(tsv_data, masked_dataset_path)

                # now do the same for bundle 5 masking
                tsv_data = parse_tsv(dataset_path, mask_nel=True, mask_nerc=False)
                masked_dataset_name = os.path.basename(dataset_path).replace(
                    "-test-", "-test-masked-bundle5-"
                )
                masked_dataset_path = os.path.join(
                    output_dir, version, lang, masked_dataset_name
                )
                write_tsv(tsv_data, masked_dataset_path)


def create_dataset(
    files: str, language: str, split: str, version: str, output_dir: str
) -> str:

    tsv_filename = f"HIPE-data-{version}-{split}-{language}.tsv"
    basedir = os.path.join(output_dir, version, language)

    if not os.path.exists(basedir):
        Path(basedir).mkdir(exist_ok=True)

    output_path = os.path.join(basedir, tsv_filename)
    concat_tsv_files(output_path, files)
    LOGGER.info(f"Written {split}-{language} to {output_path}")
    return output_path


def main(args):
    set = args["--set"]
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

    accepted_sets = ["all", "sample"]
    assert set in accepted_sets

    if set == "sample":
        create_sample(input_dir, output_dir, data_version)
    elif set == "all":
        create_datasets(input_dir, output_dir, data_version)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
