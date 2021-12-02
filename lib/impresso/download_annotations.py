"""
Script to download HIPE annotated documents from INCEpTION.

Since different annotators worked on different layers of annotations (NERC and NEL), we rely on an external
spreadsheet to determine whose annotations are to be trusted as the final version of the annotated document.

NB: to be able to run this script you need to be a user who has the rights to make API calls to an INCEpTION instance.

Usage:
    lib/download_annotations.py --corpus=<c> --input-dir=<id> --output-dir=<od> --log-file=<log> [--nerc-only]
"""  # noqa

from __future__ import print_function

import ipdb as pdb
import json
import logging
import os
import os.path
import pathlib
from pathlib import Path
from typing import List

import pandas as pd
from docopt import docopt
from tqdm import tqdm

from helpers.inception import (
    download_document,
    find_project_by_name,
    index_project_documents,
    make_inception_client,
)

# inception projects whose name contains this prefix are considered as
# containing double annotations, thus receive a special treatment
# compared to other projects
DOUBLE_ANNOTATION_PREFIX = "doubleannot"


def read_annotation_assignments(corpus: str, input_dir: str) -> pd.DataFrame:
    """Reads a CSV export of annotation assignment spreadsheet into a DataFrame.

    :param str corpus: Description of parameter `corpus`.
    :param str input_dir: Description of parameter `input_dir`.
    :return: A pandas DataFrame
    :rtype: pd.DataFrame

    """
    assignments_csv_path = (
        f"{os.path.join(input_dir, f'annotator-planning_status-corpus-{corpus}.csv')}"
    )
    assert os.path.exists(assignments_csv_path)
    return pd.read_csv(assignments_csv_path, encoding="utf-8")


def run_download_doubleannotations(
    corpus: str, input_dir: str, output_dir: str
) -> None:
    """Downloads double annotated documents from INCEpTION.

    The script uses an external spreadsheet to determine whose annotations
    are to be trusted as the final version of the annotated document.

    :param str corpus: Language of annotated documents.
    :param str input_dir: Path of input directory.
    :param str output_dir: Path of output directory where to download annotated documents.
    :param bool nerc_only: Description of parameter `nerc_only`.
    :return: Does not return anything.
    :rtype: None

    """

    # create the inception pycaprio client
    inception_client = make_inception_client()

    _, layer, language = corpus.split("-")

    # read annotation assignments for all annotated documents
    assignees_df = read_annotation_assignments(language, input_dir)

    # create a couple of inverted indexes to be able to roundtrip from document name (canonical) to
    # inception document ID and viceversa
    inception_project = find_project_by_name(inception_client, corpus)
    idx_id2name, idx_name2id = index_project_documents(
        inception_project.project_id, inception_client
    )

    # create the download folder if not yet existing
    download_dir = os.path.join(output_dir, layer.lower(), language)
    Path(download_dir).mkdir(exist_ok=True)

    # TODO: from here onwards needs to be adapted
    column_prefix = "EL double" if layer == "NEL" else "NERC double"
    finished_df = assignees_df[(assignees_df[f"{column_prefix} status"] == "done")]

    for index, row in tqdm(list(finished_df.iterrows())):

        assignee = row[f"{column_prefix} assignee"]
        document_name = row["Document ID"]
        if "NZZ" in document_name and ".txt" in document_name:
            document_name = document_name.replace(".txt", ".xmi")
        try:
            assert document_name in idx_name2id
        except AssertionError:
            logging.error(f"{document_name} not found in {inception_project}")
            continue
        document_inception_id = idx_name2id[document_name]

        # import ipdb; ipdb.set_trace()

        download_document(
            document_id=document_inception_id,
            project_id=inception_project.project_id,
            output_dir=download_dir,
            user=assignee,
            inception_client=inception_client,
        )


def run_download_annotations(
    corpus: str, input_dir: str, output_dir: str, nerc_only: bool = False
) -> None:
    """Downloads annotated documents from INCEpTION.

    This function relies on the fact that HIPE project names in INCEpTION comply to the following template:
    `impresso-corpus-{lang}`. Also, the script uses an external spreadsheet to determine whose annotations
    are to be trusted as the final version of the annotated document.

    :param str corpus: Language of annotated documents.
    :param str input_dir: Path of input directory.
    :param str output_dir: Path of output directory where to download annotated documents.
    :param bool nerc_only: Description of parameter `nerc_only`.
    :return: Does not return anything.
    :rtype: None

    """

    # create the inception pycaprio client
    inception_client = make_inception_client()

    # read annotation assignments for all annotated documents
    assignees_df = read_annotation_assignments(corpus, input_dir)

    # create a couple of inverted indexes to be able to roundtrip from document name (canonical) to
    # inception document ID and viceversa
    inception_project = find_project_by_name(
        inception_client, f"impresso-corpus-{corpus}"
    )
    idx_id2name, idx_name2id = index_project_documents(
        inception_project.project_id, inception_client
    )

    # create the download folder if not yet existing
    download_dir = os.path.join(output_dir, corpus)
    Path(download_dir).mkdir(exist_ok=True)

    if nerc_only:
        # which documents are NERC annotated
        finished_df = assignees_df[assignees_df["NERC status"] == "done"]

        logging.info(f"There are {finished_df.shape[0]} NERC annotated documents; ")

        for index, row in tqdm(list(finished_df.iterrows())):

            assignee = row["NERC assignee"]
            document_name = row["Document ID"]

            try:
                assert document_name in idx_name2id
            except AssertionError:
                logging.error(f"{document_name} not found in {inception_project}")
                continue

            document_inception_id = idx_name2id[document_name]

            download_document(
                document_id=document_inception_id,
                project_id=inception_project.project_id,
                output_dir=download_dir,
                user=assignee,
                inception_client=inception_client,
            )
    else:
        # which documents are fully annotated? (NERC + NEL)
        finished_df = assignees_df[
            (assignees_df["NEL status"] == "done")
            & (assignees_df["NERC status"] == "done")
        ]

        # how many are ready for NEL annotations?
        n_nerc_finished = assignees_df[
            (assignees_df["NEL status"] != "done")
            & (assignees_df["NERC status"] == "done")
        ].shape[0]

        logging.info(
            (
                f"There are {finished_df.shape[0]} finished documents; "
                f"{n_nerc_finished} documents are ready for NEL annotations."
            )
        )

        for index, row in tqdm(list(finished_df.iterrows())):

            assignee = row["NEL assignee"]
            document_name = row["Document ID"]
            try:
                assert document_name in idx_name2id
            except AssertionError:
                logging.error(f"{document_name} not found in {inception_project}")
                continue
            document_inception_id = idx_name2id[document_name]

            download_document(
                document_id=document_inception_id,
                project_id=inception_project.project_id,
                output_dir=download_dir,
                user=assignee,
                inception_client=inception_client,
            )


def main(args):

    corpus = args["--corpus"]
    input_dir = args["--input-dir"]
    output_dir = args["--output-dir"]
    log_file = args["--log-file"]
    nerc_only = args["--nerc-only"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    if DOUBLE_ANNOTATION_PREFIX in corpus:
        run_download_doubleannotations(corpus, input_dir, output_dir)
    else:
        run_download_annotations(corpus, input_dir, output_dir, nerc_only)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
