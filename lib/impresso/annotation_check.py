#!/usr/bin/env python
# coding: utf-8
"""
Script to create statistics about inconsistent annotations for HIPE shared task..

Usage:
    lib/annotation_check.py --f=<fpath> --output-dir=<od> --log-file=<log> [options]

Options:
    -h --help               Show this screen.
    -f --file=<fpath>       File path to pickled pandas dataframe.
    --output-dir=<od>       Output directory where the plots are saved.
    --log-file=<log>        Name of log file.
    --lang=<lang>           Langue to produce statistics.
    --method=<meth>         Method to cluster surface forms (lower, fuzzy, fuzzy-stem) [default: lower].
    --threshold=<n>         Ignore entity-link-combinations below threshold [default: 0].
    --separate-lit-meto     Analyze metonymic and literal annotation separately.
    --only-ambigious        Skip cases where there is only a single surface-link combination.
"""

from collections import defaultdict
import json
import logging
from pathlib import Path

import pandas as pd
from fuzzywuzzy import process
from fuzzywuzzy import fuzz
from docopt import docopt


def load_dataframe(file_path: str) -> pd.DataFrame:

    logging.info(f"Loaded dataframe from {file_path}")

    return pd.read_pickle(file_path)


def prepare_dataset(df, language, is_literal=None):
    # df = df.fillna('Not available')
    df = df[df.wikidata_id.notnull()]
    df["wikidata_id"].replace({"https:", "http:"}, inplace=True)

    df = df[df["language"] == language]

    if is_literal is True:
        df = df[df.is_literal == True]
    elif is_literal is False:
        df = df[df.is_literal == False]

    return df


def get_unique_items(df, surface_form):
    df_cluster = (
        df.groupby([surface_form, "wikidata_id"])
        .agg({"wikidata_id": "count", "doc_id": lambda x: x.unique().tolist()})
        .rename(columns={"wikidata_id": "count", "doc_id": "docs"})
        .reset_index()
        .sort_values("count")
    )

    df_cluster["total_surface"] = df_cluster.groupby(surface_form)["count"].transform("sum")
    df_cluster["total_id"] = df_cluster.groupby("wikidata_id")["count"].transform("sum")
    df_cluster["share_id"] = df_cluster["count"] / df_cluster["total_id"]
    df_cluster["share_surface"] = df_cluster["count"] / df_cluster["total_surface"]

    return df_cluster


def group2json(df, groupby, fname, only_ambigious=False):
    """
    Write group object into a nested json file
    """

    grouped = df.groupby(groupby)
    coarse_col = "wikidata_id" if groupby == "cluster" else "cluster"

    results = {}

    for index, nested_rows in grouped:

        fine = defaultdict(list)

        for _, row in nested_rows.sort_values("count", ascending=False).iterrows():
            fine[row[coarse_col]].append(row.to_dict())

            # coarse collects a single attribute only (i.e., link, surface cluster)
            # fine collects all the information for each entity-link combinations
            # subgrouped by the coarse_col
            if only_ambigious and len(fine) < 2:
                continue
            else:
                results[index] = {"coarse": list(fine.keys()), "fine": fine}

    with open(fname, "w", encoding='utf-8') as f:
        f.write(json.dumps(results, sort_keys=True, ensure_ascii=False))


def group2csv(df, groupby, fname, only_ambigious=False):
    """
    Write flattened group object in csv
    """

    grouped = df.groupby(groupby)

    results = []

    for index, nested_rows in grouped:
        r = []

        for _, row in nested_rows.sort_values("count", ascending=False).iterrows():
            if groupby == "cluster":
                r = [index, row["wikidata_id"], row["count"]]
            else:
                r = [index, row["surface_lower"], row["count"]]
            results.append(r)

        flat_df = pd.DataFrame(results)
        header = [groupby, "QID", "count"] if groupby == "cluster" else [groupby, "surface", "count"]
        flat_df.to_csv(fname, index=False, header=header, encoding='utf-8')


def fuzzy_mapping(df, col="surface_lower", score_cutoff=80):
    mappings = {}

    for _, cand in df.iterrows():

        cand_text = cand[col]

        # avoid redundant computations
        if cand_text in mappings:
            continue

        matches = process.extractBests(
            cand[col], df[col].unique(), score_cutoff=score_cutoff, scorer=fuzz.ratio
        )

        # point to most frequent match
        main_count = 0
        for match, score in matches:
            count = int(df[df[col] == match].sort_values("count", ascending=False).iloc[0]["count"])
            if count > main_count:
                main_match = match
                main_count = count

        mappings[cand_text] = main_match

    return mappings


def plot_surface_distribution(df, fname=None):

    df_var = (
        df.groupby("wikidata_id")["cluster"]
        .count()
        .reset_index()
        .rename(columns={"cluster": "n_surfaces_per_link", "wikidata_id": "links"})
    )
    df_var = df_var.groupby(["n_surfaces_per_link"]).count()

    fig = df_var.plot.bar(rot=0, title="surface distribution per link", logy=True).get_figure()
    if fname:
        fig.savefig(fname)

    return fig


def plot_link_distribution(df, fname=None):

    df_var = (
        df.groupby("cluster")["wikidata_id"]
        .count()
        .reset_index()
        .rename(columns={"wikidata_id": "n_links_per_surface"})
    )
    df_var = df_var.groupby(["n_links_per_surface"]).count()

    fig = df_var.plot.bar(rot=0, title="link distribution per surface", logy=True).get_figure()

    if fname:
        fig.savefig(fname)

    return fig


def plot_link_distribution_across_lang(df):
    df_items = (
        df.groupby(["language", "surface", "wikidata_id"])
        .agg({"wikidata_id": "count", "doc_id": lambda x: x.unique().tolist()})
        .rename(columns={"wikidata_id": "count", "doc_id": "docs"})
        .reset_index()
        .sort_values("count")
    )
    df_var = (
        df_items.groupby(["language", "wikidata_id"])["surface"]
        .count()
        .reset_index()
        .rename(columns={"surface": "n_surfaces_per_link", "wikidata_id": "cases"})
    )
    df_var = df_var.groupby(["n_surfaces_per_link", "language"]).count()

    ax = df_var.unstack().plot.bar(rot=0, title="surface distribution per link", logy=True)
    ax.legend(["German", "English", "French"])
    fig = ax.get_figure()
    fig.savefig("barplot_surface_distribution_per_link.png")


def consistency_checks(
    fname, lang="de", method="lower", threshold=0, dir_out="", is_literal=None, only_ambigious=False
):

    dir_out.mkdir(parents=True, exist_ok=True)

    df = load_dataframe(fname)
    df_lang = prepare_dataset(df, lang, is_literal=is_literal)

    df_lang["surface_lower"] = df["surface"].str.lower()

    df_items = get_unique_items(df_lang, "surface_lower")

    if method == "lower":
        df_items["cluster"] = df_items["surface_lower"]

    elif method == "fuzzy":
        mappings = fuzzy_mapping(df_items)
        df_items["cluster"] = df_items["surface_lower"].map(mappings)

    elif method == "fuzzy-stem":
        # compute clusters on lowercase and alphanumeric symbols only
        df_items["surface_stem"] = df_items["surface_lower"].str.replace(r"[^\w ]", "")
        mappings = fuzzy_mapping(df_items, col="surface_stem", score_cutoff=90)
        df_items["cluster"] = df_items["surface_stem"].map(mappings)

    if threshold > 0:
        df_items = df_items[df_items["count"] >= threshold]

    # cluster by surface form
    fname = dir_out / f"{lang}_{method}_cluster_by_surface.json"
    group2json(df_items, groupby="cluster", fname=fname, only_ambigious=only_ambigious)
    fname = dir_out / f"{lang}_{method}_cluster_by_surface.csv"
    group2csv(df_items, groupby="cluster", fname=fname, only_ambigious=only_ambigious)

    # cluster by wikidata id
    fname = dir_out / f"{lang}_{method}_cluster_by_link.json"
    group2json(df_items, groupby="wikidata_id", fname=fname, only_ambigious=only_ambigious)
    fname = dir_out / f"{lang}_{method}_cluster_by_link.csv"
    group2csv(df_items, groupby="wikidata_id", fname=fname, only_ambigious=only_ambigious)

    # plot ratios number of links per surface and number of surfaces per link
    fname = dir_out / f"{lang}_{method}_barplot_surface_distribution_per_link.png"
    plot_surface_distribution(df_items, fname)
    fname = dir_out / f"{lang}_{method}_barplot_link_distribution_per_link.png"
    plot_link_distribution(df_items, fname)

    return df_items


def main(args):

    data = args["--f"]
    output_dir = args["--output-dir"]
    log_file = args["--log-file"]
    threshold = int(args["--threshold"])
    method = args["--method"]
    lang = args["--lang"]
    separate = args["--separate-lit-meto"]
    only_ambigious = args["--only-ambigious"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    dir_out = Path(output_dir)

    if separate:
        for anno_type, is_literal in [("literal", True), ("metonymic", False)]:
            dir_sub = dir_out / anno_type
            consistency_checks(
                data,
                lang=lang,
                method=method,
                threshold=threshold,
                dir_out=dir_sub,
                is_literal=is_literal,
                only_ambigious=only_ambigious,
            )
    else:
        consistency_checks(
            data,
            lang=lang,
            method=method,
            threshold=threshold,
            dir_out=dir_out,
            only_ambigious=only_ambigious,
        )

    logging.info(f"Finished. Saved stats to {output_dir}")


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
