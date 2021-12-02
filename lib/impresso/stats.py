"""
Script to produce statistics about annotated data for HIPE shared task.

Usage:
    lib/stats.py --input-dir=<id> --output-dir=<od> --log-file=<log> [--refresh]
"""  # noqa

import glob
import json
import logging
import os
import os.path
import pathlib
from pathlib import Path
from typing import List
from textwrap import dedent

import ipdb  # TODO: remove from production
import matplotlib.pyplot as plt
import pandas as pd
import tabulate
from docopt import docopt
from tqdm import tqdm

from helpers.inception import read_xmi_for_stats
from helpers.stats import (
    create_entity_dataframes,
    create_metadata_dataframes,
    read_split_assignments,
)
from helpers import clean_directory


def save_dataframe(df: pd.DataFrame, filename: str, output_dir: str) -> None:

    df.to_pickle(os.path.join(output_dir, f"{filename}.pkl"))
    df.to_csv(os.path.join(output_dir, f"{filename}.csv"))


def load_dataframe(filename: str, input_dir: str) -> pd.DataFrame:

    file_path = os.path.join(input_dir, f"{filename}.pkl")
    logging.info(f"Loaded dataframe from {file_path}")
    return pd.read_pickle(file_path)


def compile_stats_report(filename: str, annotation_type: str, plots_dir: str, output_dir: str):

    report_path = os.path.join(output_dir, filename)
    md_overview_table = read_md_table(f"{annotation_type}_overview_table.md", output_dir)
    md_mention_types_table = read_md_table(f"{annotation_type}_mention_types_table.md", output_dir)
    md_nil_types_table = read_md_table(f"{annotation_type}_nil_coarse_types_table.md", output_dir)

    md_report = f"""
    #### Statistics about HIPE data release v0.9

    Computed on version `v0.9` of our datasets;  last update: 20 February 2020.

    **Overview**

    {md_overview_table}

    As a reminder, we are not releasing training data for English.

    **Number of documents by decade**

    ![alt]({os.path.join('plots', f"{annotation_type}_n_documents_diachronic.png")})

    **Number of tokens by decade**

    ![alt]({os.path.join('plots', f"{annotation_type}_n_tokens_diachronic.png")})

    **Number of mentions by decade**

    ![alt]({os.path.join('plots', f"{annotation_type}_n_mentions_diachronic.png")})

    **Number of  mentions, broken down by type (coarse)**

    {md_mention_types_table}

    **Number of mentions, broken down by type (coarse)**

    ![alt]({os.path.join('plots', f"{annotation_type}_coarse_types_diachronic.png")})

    **Metonymy**

    ![alt]({os.path.join('plots', f"{annotation_type}_mentonymy_diachronic.png")})

    ![alt]({os.path.join('plots', f"{annotation_type}_mentonymy_by_language_diachronic.png")})
    """

    if annotation_type == "full":
        md_report += f"""
        **NIL entities ratio**

        We link mentions against Wikidata. NIL entities are those that do not have a corresponding entry in Wikidata.

        Number of NIL entities over the total number of mentions (per decade):

        ![alt]({os.path.join('plots', "nil_ratio_diachronic.png")})

        **NIL entities by mention type (coarse)**
        {md_nil_types_table}
        """

    report_dedented = "\n".join([line.strip() for line in md_report.split("\n")])

    with open(report_path, "w") as f:
        f.write(report_dedented)


def save_md_table(
    df: pd.DataFrame, headers: List[str], filename: str, annotation_type: str, output_dir: str,
) -> None:

    md_table_path = os.path.join(output_dir, f"{annotation_type}_{filename}")
    md_table = tabulate.tabulate(df, tablefmt="pipe", headers=headers,)

    with open(md_table_path, "w") as outfile:
        outfile.write(md_table)


def read_md_table(filename: str, input_dir: str) -> str:

    md_table = None
    md_table_path = os.path.join(input_dir, filename)
    with open(md_table_path, "r") as f:
        md_table = f.read()
    return md_table


def produce_mentions_stats(
    mentions_df: pd.DataFrame,
    document_metadata_df: pd.DataFrame,
    annotation_type: str,
    output_dir: str,
    plots_dir: str,
) -> None:
    #####################################
    # 1) number of mentions by language #
    #####################################
    ax = (
        pd.DataFrame(
            mentions_df[mentions_df.entity_coarse != "comp"]
            .groupby(by=["decade", "language"])
            .size()
        )
        .rename({0: "n_mentions"}, axis=1)
        .fillna(0)
        .unstack()
        .fillna(0)
        .astype(int)
        .plot(
            kind="bar", figsize=(10, 8), title=f"Number of mentions by decade ({annotation_type})",
        )
    )
    ax.legend(["German", "English", "French"])
    fig = ax.get_figure()
    plot_name = f"{annotation_type}_n_mentions_diachronic.png"
    fig.savefig(os.path.join(plots_dir, plot_name), dpi=300)

    ####################################
    # 2) number of mentions by decade  #
    ####################################
    ax = (
        pd.DataFrame(mentions_df[mentions_df.entity_coarse != "comp"].groupby(by="decade").size())
        .rename({0: "n_mentions"}, axis=1)
        .plot(kind="bar", figsize=(10, 8), title="Number of mentions by decade", legend=False,)
    )
    fig = ax.get_figure()
    plot_name = f"{annotation_type}_n_mentions_diachronic.png"
    fig.savefig(os.path.join(plots_dir, plot_name), dpi=300)

    #################################################
    # 3) create table with mentions by coarse type  #
    #################################################
    mention_types_df = pd.DataFrame(
        mentions_df[mentions_df.entity_coarse != "comp"].groupby(by="entity_coarse").size()
    ).rename({0: "n_mentions"}, axis=1)

    save_md_table(
        mention_types_df.sort_values(by="n_mentions", ascending=False),
        ["coarse type", "# of mentions"],
        "mention_types_table.md",
        annotation_type,
        output_dir,
    )

    ###########################################
    # 4) diachronic breakdown of coarse types #
    ###########################################
    diachronic_mentions_df = pd.DataFrame(
        mentions_df[mentions_df.entity_coarse != "comp"]
        .groupby(by=["decade", "entity_coarse"])
        .size()
    ).rename({0: "n_mentions"}, axis=1)

    # to calculate an average we need to know how many documents per decade
    n_docs_decade_df = pd.DataFrame(document_metadata_df.groupby(by=["decade"]).size()).rename(
        {0: "n_documents"}, axis=1
    )

    diachronic_mentions_df = diachronic_mentions_df.join(n_docs_decade_df)
    diachronic_mentions_df["avg_mentions"] = (
        diachronic_mentions_df.n_mentions / diachronic_mentions_df.n_documents
    )

    ax = (
        diachronic_mentions_df[["avg_mentions"]]
        .fillna(0.0)
        .unstack()
        .fillna(0.0)
        .plot(kind="bar", figsize=(10, 16), subplots=True, sharey=True, title=["", "", "", "", ""],)
    )
    ax[0].legend(["loc"])
    ax[1].legend(["org"])
    ax[2].legend(["pers"])
    ax[3].legend(["prod"])
    ax[4].legend(["time"])

    plot_name = f"{annotation_type}_coarse_types_diachronic.png"
    plt.savefig(os.path.join(plots_dir, plot_name), dpi=300)

    #####################################
    # 5) includes stats about metonymy  #
    #####################################

    met_mentions_df = mentions_df[mentions_df.is_literal]
    met_mentions_df.groupby("entity_coarse").size().sort_values(ascending=False)

    # first metonymy plot
    ax = (
        pd.DataFrame(met_mentions_df.groupby(by="decade").size())
        .rename({0: "n_mentions"}, axis=1)
        .plot(kind="bar", figsize=(10, 8), title="Metonymic mentions/entities by decade")
    )
    fig = ax.get_figure()
    plot_name = f"{annotation_type}_mentonymy_diachronic.png"
    fig.savefig(os.path.join(plots_dir, plot_name), dpi=300)

    # second metonymy plot
    ax = (
        pd.DataFrame(met_mentions_df.groupby(by=["decade", "language"]).size())
        .rename({0: "n_mentions"}, axis=1)
        .fillna(0)
        .unstack()
        .fillna(0)
        .astype(int)
        .plot(kind="bar", figsize=(10, 8), title="Metonymic mentions/entities by language")
    )
    ax.legend(["German", "English", "French"])

    fig = ax.get_figure()
    plot_name = f"{annotation_type}_mentonymy_by_language_diachronic.png"
    fig.savefig(os.path.join(plots_dir, plot_name), dpi=300)


def produce_linking_stats(
    entities_df: pd.DataFrame, mentions_df: pd.DataFrame, output_dir: str, plots_dir: str,
):
    # filter only NIL entities
    nil_entities_df = entities_df[entities_df.is_NIL]

    # group NIL entities by decade
    nil_decade_df = pd.DataFrame(nil_entities_df.groupby(by="decade").size()).rename(
        {0: "n_nil"}, axis=1
    )

    # get total number of entities/mentions per decade
    n_entities_decade_df = pd.DataFrame(
        mentions_df[mentions_df.entity_coarse != "comp"].groupby("decade").size()
    ).rename({0: "n_entities"}, axis=1)
    nil_decade_df = nil_decade_df.join(n_entities_decade_df)

    # finally compute the raion of NIL as a percentage
    nil_decade_df["nil_ratio"] = (nil_decade_df.n_nil * 100) / nil_decade_df.n_entities

    # plotty plot
    ax = nil_decade_df[["nil_ratio"]].plot(
        kind="bar", figsize=(10, 8), title="Ratio of NIL entities by decade", legend=False,
    )
    ax.set_ylabel("ratio (%)")
    ax.set_xlabel("")
    fig = ax.get_figure()
    plot_name = "nil_ratio_diachronic.png"
    fig.savefig(os.path.join(plots_dir, plot_name), dpi=300)

    # and finally we cacluate the number of NIL by coarse types
    entities_df["uid"] = entities_df.apply(lambda r: f"{r['doc_id']}#{r['entity_id']}", axis=1)
    entities_df.set_index("uid", inplace=True)
    mentions_df["uid"] = mentions_df.apply(lambda r: f"{r['doc_id']}#{r['annotation_id']}", axis=1)
    mentions_df.set_index("uid", inplace=True)
    entities_df = entities_df.join(mentions_df[["entity_coarse"]])

    entities_coarse_types_df = pd.DataFrame(
        entities_df[
            (entities_df.is_NIL) & (entities_df.entity_coarse.isin(["pers", "loc", "org"]))
        ].entity_coarse.value_counts()
    )
    save_md_table(
        entities_coarse_types_df,
        ["coarse type", "# of NIL entities"],
        "nil_coarse_types_table.md",
        "full",
        output_dir,
    )


def produce_overview_stats(
    corpus_metadata_df, document_metadata_df, annotation_type, output_dir, plots_dir
) -> None:
    """Produces tables and plots about number/distribution of documents/tokens in the corpus.

    :param type corpus_metadata_df: Description of parameter `corpus_metadata_df`.
    :param type document_metadata_df: Description of parameter `document_metadata_df`.
    :param type annotation_type: Description of parameter `annotation_type`.
    :param type output_dir: Description of parameter `output_dir`.
    :param type plots_dir: Description of parameter `plots_dir`.
    :return: Description of returned object.
    :rtype: None

    """

    assert annotation_type in ["full", "nerc"]

    # let's start with a table
    overview_df = corpus_metadata_df[["n_documents"]].join(
        document_metadata_df.groupby(by="language").agg({"n_tokens": sum, "n_mentions": sum})
    )
    md_table_path = os.path.join(output_dir, f"{annotation_type}_overview_table.md")
    hs = ["language", "# of documents", "# of tokens", "# of mentions"]
    md_table = tabulate.tabulate(overview_df, tablefmt="pipe", headers=hs)

    with open(md_table_path, "w") as outfile:
        outfile.write(md_table)

    # plot distribution of documents
    ax = (
        pd.DataFrame(document_metadata_df.groupby(by="decade").size())
        .rename({0: "n_documents"}, axis=1)
        .plot(
            kind="bar",
            figsize=(10, 8),
            title=f"Number of documents by decade ({annotation_type})",
            legend=False,
        )
    )
    fig = ax.get_figure()
    plot_name = f"{annotation_type}_n_documents_diachronic.png"
    fig.savefig(os.path.join(plots_dir, plot_name), dpi=300)

    # plot distribution of tokens
    ax = (
        document_metadata_df.groupby(by=["decade", "language"])
        .agg({"n_tokens": sum})
        .fillna(0)
        .unstack()
        .fillna(0)
        .astype(int)
        .plot(kind="bar", figsize=(10, 8), title="Number of tokens by language by decade")
    )
    ax.legend(["German", "English", "French"])

    fig = ax.get_figure()
    plot_name = f"{annotation_type}_n_tokens_diachronic.png"
    fig.savefig(os.path.join(plots_dir, plot_name), dpi=300)


def produce_stats(input_dir: str, output_dir: str, refresh: bool):

    stats_dir = output_dir
    plots_dir = os.path.join(stats_dir, "plots")
    serialized_data_dir = os.path.join(stats_dir, "data")

    clean_directory(plots_dir)

    if refresh:

        # clean the data folder before retrieving the new data
        clean_directory(serialized_data_dir)

        # create some dataframes with corpus- and document-level stats
        full_corpus_metadata_df, full_document_metadata_df = create_metadata_dataframes(
            os.path.join(input_dir, "annotated")
        )

        # TODO: at this point, keep only documents that are found in valid splits
        assignments_df = read_split_assignments(input_dir)
        full_document_metadata_df = full_document_metadata_df.join(assignments_df, how="inner")
        valid_splits = ["dev", "train", "test"]
        unassigned_docs = full_document_metadata_df[
            ~full_document_metadata_df.Split.isin(valid_splits)
        ].index.to_list()
        print(f"There are {len(unassigned_docs)} unassigned documents")
        print(f"Unassigned documents {unassigned_docs}")
        full_document_metadata_df = full_document_metadata_df[
            full_document_metadata_df.Split.isin(valid_splits)
        ]

        # nerc_corpus_metadata_df, nerc_document_metadata_df = create_metadata_dataframes(
        #    os.path.join(input_dir, 'annotated_nerc')
        # )

        # create some dataframes with mentions and entities information
        (full_document_metadata_df, full_mentions_df, full_entities_df,) = create_entity_dataframes(
            full_document_metadata_df
        )
        # nerc_document_metadata_df, nerc_mentions_df = create_entity_dataframes(nerc_document_metadata_df, True)

        # NERC + NEL annotations
        save_dataframe(full_corpus_metadata_df, "full_corpus-metadata_df", serialized_data_dir)
        save_dataframe(full_document_metadata_df, "full_document-metadata_df", serialized_data_dir)
        save_dataframe(full_mentions_df, "full_mentions_df", serialized_data_dir)
        save_dataframe(full_entities_df, "full_entities_df", serialized_data_dir)

        # NERC only annotations
        # save_dataframe(nerc_corpus_metadata_df, 'nerc_corpus-metadata_df', serialized_data_dir)
        # save_dataframe(nerc_document_metadata_df, 'nerc_document-metadata_df', serialized_data_dir)
        # save_dataframe(nerc_mentions_df, 'nerc_mentions_df', serialized_data_dir)
    else:
        # NERC + NEL annotations
        full_corpus_metadata_df = load_dataframe("full_corpus-metadata_df", serialized_data_dir)
        full_document_metadata_df = load_dataframe("full_document-metadata_df", serialized_data_dir)
        full_mentions_df = load_dataframe("full_mentions_df", serialized_data_dir)
        full_entities_df = load_dataframe("full_entities_df", serialized_data_dir)

        # NERC only annotations
        # nerc_corpus_metadata_df = load_dataframe('nerc_corpus-metadata_df', serialized_data_dir)
        # nerc_document_metadata_df = load_dataframe('nerc_document-metadata_df', serialized_data_dir)
        # nerc_mentions_df = load_dataframe('nerc_mentions_df', serialized_data_dir)

    # data massage
    full_document_metadata_df["decade"] = full_document_metadata_df.year.apply(
        lambda y: int(f"{str(y)[:3]}0")
    )
    full_mentions_df.doc_id = full_mentions_df.doc_id.apply(lambda d: d.split(".")[0])
    full_mentions_df = full_mentions_df.join(full_document_metadata_df[["decade"]], on="doc_id")

    full_document_metadata_df["decade"] = full_document_metadata_df.year.apply(
        lambda y: int(f"{str(y)[:3]}0")
    )
    full_entities_df.doc_id = full_entities_df.doc_id.apply(lambda d: d.split(".")[0])
    full_entities_df = full_entities_df.join(full_document_metadata_df[["decade"]], on="doc_id")

    # nerc_document_metadata_df['decade'] = nerc_document_metadata_df.year.apply(lambda y: int(f"{str(y)[:3]}0"))
    # nerc_mentions_df.doc_id = nerc_mentions_df.doc_id.apply(lambda d: d.split(".")[0])
    # nerc_mentions_df = nerc_mentions_df.join(nerc_document_metadata_df[['decade']], on='doc_id')

    # do overview stats
    produce_overview_stats(
        full_corpus_metadata_df, full_document_metadata_df, "full", stats_dir, plots_dir
    )
    # produce_overview_stats(nerc_corpus_metadata_df, nerc_document_metadata_df, 'nerc', stats_dir, plots_dir)

    # do mentions stats
    produce_mentions_stats(
        full_mentions_df, full_document_metadata_df, "full", stats_dir, plots_dir
    )
    # produce_mentions_stats(nerc_mentions_df, nerc_document_metadata_df, 'nerc', stats_dir, plots_dir)

    # do entities stats
    produce_linking_stats(full_entities_df, full_mentions_df, stats_dir, plots_dir)

    # finally create the reports
    compile_stats_report("stats_report_full.md", "full", plots_dir, stats_dir)
    # compile_stats_report('stats_report_nerc.md', 'nerc', plots_dir, stats_dir)


def main(args):

    input_dir = args["--input-dir"]
    output_dir = args["--output-dir"]
    log_file = args["--log-file"]
    refresh = args["--refresh"] if args["--refresh"] else False

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    produce_stats(input_dir, output_dir, refresh)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
