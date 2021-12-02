#!/usr/bin/env python
# coding: utf-8

"""
Leverage the system responses to spot potentially wrong annotations in the gold standard.

Whenever a majority of systems (or any other threshold) predicts another annotation
as there is in the gold standard, it gets logged.

Usage:
    lib/aggregate_system_responses.py --gold_file=<fpath> --input_dir=<id> --log_file=<log> [options]

Options:
    -h --help               Show this screen.
    -f --gold_file=<fpath>  File path to gold standard.
    -i --input_dir=<id>     Input directory where the system responses are saved.
    -t --threshold=<float>  Log when system predicted the true label below this threshold [default:0.5]
    -l --log_file=<log>     Name of log file.
"""

import logging
from pathlib import Path
import csv
from collections import OrderedDict

import pandas as pd
import numpy as np
from docopt import docopt


def index_files(dir_data, lang, suffix=".tsv") -> list:
    """Index all .tsv files for a specific language in the provided directory

    :param str dir_data: Path to top-level dir.
    :param str suffix: Only consider files of this type.
    :param str lang: Language that needs to be part of the base filename.
    :return: List of found files.
    :rtype: list

    """

    return sorted([path for path in Path(dir_data).rglob(f"*_{lang}_*" + suffix)])


def read_dataframe(f_sub: str) -> pd.DataFrame:
    """
    Read a a dataframe, filter out comments, and keep NEL best@1 only.
    """

    df = pd.read_csv(f_sub, sep="\t", quoting=csv.QUOTE_NONE, quotechar="")
    # remove any comments
    df = df[~df.TOKEN.str.startswith("# ", na=True)].reset_index()

    # keep NEL best@1 only
    try:
        df = df.fillna(value={"NE-COARSE-LIT": "", "NEL-LIT": "", "NEL-METO": ""})
        df["NEL-LIT"] = df["NEL-LIT"].str.split("|").apply(lambda x: x[:1])
        df["NEL-METO"] = df["NEL-METO"].str.split("|").apply(lambda x: x[:1])

        df["NEL-METO"] = df["NEL-METO"].str.join("|")
        df["NEL-LIT"] = df["NEL-LIT"].str.join("|")

    except KeyError:
        pass

    return df


def select_annotation(dfs_submission: list, col: str) -> list:
    """
    Filter dataframes and columns that have revevant data for a particular annotation type.
    """
    dfs_filtered = []
    for df in dfs_submission:
        try:
            labels = set(df[col].unique())
            labels = {label for label in labels if labels not in {"_", "O"}}
            if len(labels) > 1:
                dfs_filtered.append(df[col])
        except KeyError:
            # ignore datasets that do not provide annotations for this paritcular column
            continue

    logging.info(f"Number of system responses for column '{col}': {len(dfs_filtered)}\n\n")

    return dfs_filtered


def assert_equal_length(df_gold: pd.DataFrame, df_subs: list, submissions: list):
    """
    Exclude datasets that are longer than gold standard
    """

    df_filtered = []
    try:
        for i, df in enumerate(df_subs):
            assert len(df) == len(df_gold)
            df_filtered.append(df)
    except AssertionError:
        logging.info(
            f"Excluded dataset that do not match length of the gold standard: {submissions[i]}"
        )
        pass

    return df_filtered


def aggregate_responses(
    df_gold: pd.DataFrame, dfs_submission: list, threshold=0.5, log_once_per_label=True
):
    """
    Log all gold standard annotations (any column for NERC, NEL)
    for which system predictions are below a particular threshold.
    """

    columns = [item for item in df_gold.columns if item not in {"index", "TOKEN", "MISC"}]

    dfs_submission = [df for df in dfs_submission if len(df) == len(df_gold)]

    for col in columns:
        dfs_filtered = select_annotation(dfs_submission, col)
        df_aggr = pd.concat(dfs_filtered, axis=1)

        # add column with entity surface
        df_gold["KEY"] = (df_gold[col] != df_gold[col].shift(1)).astype(int).cumsum()
        df_gold["SURFACE"] = df_gold.groupby(["KEY", col])["TOKEN"].transform(" ".join)
        # for non-entities use current token as surface
        df_gold["SURFACE"] = np.where(
            df_gold[col].isin(["O", "-", "_"]), df_gold.TOKEN, df_gold.SURFACE
        )

        anno_gold_prev = None
        for i, row in df_aggr.iterrows():
            token = df_gold.iloc[i]["TOKEN"]
            surface = df_gold.iloc[i]["SURFACE"]
            anno_gold = df_gold.iloc[i][col]
            anno_count = OrderedDict(row.value_counts(normalize=True).to_dict())
            anno_count_common = [
                f"{label}: {frq:.2f}" for label, frq in list(anno_count.items())[:3]
            ]

            if log_once_per_label and anno_gold == anno_gold_prev:
                continue

            try:
                if anno_count[anno_gold] < threshold:
                    msg = (
                        "Systems predicted primarily other than the true label. "
                        + f"SURFACE: `{surface}`, TRUE: {anno_gold} \t PRED: {anno_count_common} \t LINE: {i}, COL: {col}"
                    )
                    logging.warning(msg)
                    anno_gold_prev = anno_gold
            except KeyError:
                msg = (
                    "No system predicted the true label. "
                    + f"SURFACE: `{surface}`, TRUE: {anno_gold} \t PRED: {anno_count_common} \t LINE: {i}, COL: {col}"
                )
                logging.warning(msg)
                anno_gold_prev = anno_gold


def main(args):

    input_dir = args["--input_dir"]
    f_gold = args["--gold_file"]
    threshold = float(args["--threshold"])
    log_file = args["--log_file"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logging.info(f"Start aggregation of system responses and compare against {f_gold}")

    df_gold = read_dataframe(f_gold)

    # parse language
    lang = f_gold.split("-")[-1].rstrip(".tsv")

    submissions = index_files(input_dir, lang=lang)
    logging.info(f"Total number of system responses: {len(submissions)}")

    dfs_submission = [read_dataframe(fname) for fname in submissions]
    dfs_submission = assert_equal_length(df_gold, dfs_submission, submissions)

    aggregate_responses(df_gold, dfs_submission, threshold=threshold)

    logging.info(f"Finished. Potentially wrong annotations are logged to {log_file}")


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
