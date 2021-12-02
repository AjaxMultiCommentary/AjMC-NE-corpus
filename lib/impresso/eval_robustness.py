"""
Script to produce the data and plots about the detailed system performance on diachronic and noisy data for HIPE shared task.

Usage:
    lib/eval_robustness.py --input-dir=<id> --output-dir=<od> --log-file=<log>
"""

import os
import logging
from docopt import docopt
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd


TEAM_MAPPINGS = {
    "team1": "ehrmama",
    "team7": "IRISA_",
    "team8": "CISTeria",
    "team10": "L3i",
    "team11": "NLP-UQAM",
    "team16": "ERTIM",
    "team23": "UPB",
    "team28": "SinNER",
    "team31": "UvA.ILPS",
    "team33": "SBB",
    "team37": "Inria-DeLFT",
    "team39": "LIMSI",
    "team40": "Webis",
}

# ensure that team1 doesn't match team10 for example
TEAM_MAPPINGS = {key + "_": val + "_" for key, val in TEAM_MAPPINGS.items()}


def read_ranking(ranking_name: str, rankings_dir: str, label="ALL") -> pd.DataFrame:

    relevant_tsv_file = os.path.join(rankings_dir, ranking_name)

    df = pd.read_csv(relevant_tsv_file, delimiter="\t")

    selected_cols = [
        "Evaluation",
        "Label",
        "F1",
        "P",
        "R",
        # 'run',
        #'F1_std','P_std', 'R_std', 'TP', 'FP','FN',
        "System",
    ]

    df = df[~(df.F1 == 0.0)]
    df = df[df.Label == label]
    df = df[~df.System.str.contains("baseline")]
    df = df[df.Evaluation.str.contains("LIT")]

    return df[selected_cols]


def get_performance_noise(df: pd.DataFrame) -> pd.DataFrame:

    # select all systems
    df_sub = df[(df.time_start.isnull()) & (~df.levenshtein.isnull())]

    return df_sub


def get_performance_time(
    df: pd.DataFrame, n_best_per_team: int = None, n_best_systems: int = None
) -> pd.DataFrame:

    # select systems on overall performance measured by F1-score
    df_systems = df[(df.time_start.isnull()) & (df.levenshtein.isnull())]

    if n_best_per_team:
        df_systems = (
            df_systems.sort_values("F1", ascending=False).groupby("team").head(n_best_per_team)
        )

    if n_best_systems:
        df_systems = df_systems.nlargest(n_best_systems, "F1")

    systems_to_show = df_systems.System.values

    # select rows for relevant systems
    df_sub = df[(~df.time_start.isnull()) & (df.levenshtein.isnull())]

    df_sub = df_sub[df_sub.System.isin(systems_to_show)]

    return df_sub


def plot_performance_time(df: pd.DataFrame, stats_dir: str, plots_dir: str, metric="F1", suffix=""):

    # plot
    sns.set_style("ticks")

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(10, 8))

    ax = sns.lineplot(data=df, x="time_start", y=metric, hue="system", style="system")
    sns.despine()

    ax.set(ylim=(0.0, 1.0))
    ax.set_title(f"Diachronic performance of best systems ({suffix})")
    ax.set_ylabel(metric)
    ax.set_xlabel("Years (bucket)")

    plt.legend(loc="lower right")

    fig = ax.get_figure()

    # export plot
    fname = f"performance_diachronic_{suffix}_{metric}"
    fig.savefig(os.path.join(plots_dir, f"{fname}.png"), dpi=300)

    plt.close()

    # export table
    df.to_csv(os.path.join(stats_dir, f"{fname}.csv"))

    return fig


def plot_performance_noise(
    df: pd.DataFrame, stats_dir: str, plots_dir: str, metric="F1", suffix=""
):

    # plot
    sns.set_style("ticks")
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(10, 8))

    sns.boxplot(data=df, x="levenshtein", y=metric)
    sns.despine()

    ax.set(ylim=(0.0, 1.0))
    ax.set_title(f"Performance distribution on noisy entities ({suffix})")
    ax.set_ylabel(f"{metric}-score")
    ax.set_xlabel("Levenshtein")

    fig = ax.get_figure()

    # export plot
    fname = f"performance_noise_{suffix}_{metric}"
    fig.savefig(os.path.join(plots_dir, f"{fname}.png"), dpi=300)

    plt.close()

    # export as table
    df.to_csv(os.path.join(stats_dir, f"{fname}.csv"))


def multiplot_performance_noise(
    df: pd.DataFrame, stats_dir: str, plots_dir: str, metric="F1", suffix=""
):

    # plot
    sns.despine()
    sns.set(font_scale=1.4)
    sns.set_style("ticks")

    # colors = ['#4c72b0', '#dd8452', '#c44e52']
    # colors = ['#4878d0', '#ee854a',  '#d65f5f']
    colors = ["#55a868", "#4c72b0", "#dd8452", "#c44e52"]
    order = ["French", "German", "English"]

    g = sns.catplot(
        data=df,
        x="levenshtein",
        y=metric,
        col="lang",
        kind="box",
        palette=sns.color_palette(colors),
        col_order=order,
    )
    g.set_axis_labels(
        "Levenshtein", f"{metric}-score",
    )
    g.set(ylim=(0.0, 1.0))
    g.set_titles("{col_name}")

    plt.subplots_adjust(top=0.85)
    # g.fig.suptitle(f"Performance distribution on noisy entities({suffix})")

    # export plot
    fname = f"performance_noise_{suffix}_{metric}"
    g.savefig(os.path.join(plots_dir, f"{fname}.png"), dpi=300)

    # export as table
    df.to_csv(os.path.join(stats_dir, f"{fname}.csv"))


def extend_dataframe(df: pd.DataFrame, lang: str) -> pd.DataFrame:

    mappings = {"de": "German", "fr": "French", "en": "English"}
    df["lang"] = mappings[lang]

    df["time_start"] = df.Evaluation.str.extract("TIME-([0-9]{4})")
    df["time_end"] = df.Evaluation.str.extract("TIME-[0-9]{4}-([0-9]{4})")
    df["levenshtein"] = df.Evaluation.str.extract("LED-([0-9.]+-?[0-9.]*)")
    df["levenshtein"] = df["levenshtein"].str.replace("1.1", "1.0")
    df["levenshtein"] = df["levenshtein"].str.replace("0.0-0.0", "0.0")
    df["levenshtein"] = df["levenshtein"].str.replace("0.001-0.1", "0.0-0.1")
    df["team"] = df.System.str.extract("^(.+?)_")

    return df


def define_sytem_label(df: pd.DataFrame) -> pd.DataFrame:

    df["system"] = df.System.replace(TEAM_MAPPINGS, regex=True)
    df["system"] = df.system.str.split("_").apply(lambda x: x[0])

    return df


def plot_all_languages_noise_diachronic(input_dir: str, output_dir: str):

    stats_dir = output_dir
    plots_dir = os.path.join(stats_dir, "plots")

    os.makedirs(plots_dir, exist_ok=True)

    for task in [
        "nerc",
        "nel_relaxed_@3",

    ]:  # "nel_@1", "nel-only_@1", "nel-only_relaxed_@3",

        for metric in ["F1"]:  # 'R', 'P'

            dfs_ocr_all = []
            dfs_time_all = []

            languages = ["de", "fr", "en"]

            for lang in languages:

                # set ranking file
                if task == "nerc":
                    ranking_file = f"ranking-{lang}-coarse-micro-fuzzy-all.tsv"
                elif "relaxed" in task:
                    ranking_file = f'ranking-{lang}-{task.split("_")[0]}-micro-fuzzy-relaxed.tsv'
                else:
                    ranking_file = f'ranking-{lang}-{task.split("_")[0]}-micro-fuzzy.tsv'

                df = read_ranking(ranking_file, input_dir, label="ALL")

                df = define_sytem_label(df)

                # select particular cutoff for NEL
                if "nel" in task:
                    cutoff = task.split("_")[-1]
                    df = df[df.Evaluation.str.contains(cutoff)]

                df = extend_dataframe(df, lang)
                df_ocr = get_performance_noise(df)
                df_time = get_performance_time(df, n_best_systems=5, n_best_per_team=1)

                regimen = df.Evaluation.str.replace(
                    ".*(LIT-micro-fuzzy).*-TIME.*LED.*(-@.)?", r"\1\2"
                ).unique()
                assert len(regimen) == 1

                suffix = f"{lang}-{task}-{regimen[0]}".upper().replace("_", "-")

                # plot particular language
                # plot_performance_time(df_time, stats_dir, plots_dir, metric=metric, suffix=suffix)
                # plot_performance_noise(df_ocr, stats_dir, plots_dir, metric=metric, suffix=suffix)

                dfs_time_all.append(df_time)
                dfs_ocr_all.append(df_ocr)

            # make noise plot with all language
            suffix = f"all-lang-{task}-{regimen[0]}".upper().replace("_", "-")

            df_ocr_all = pd.concat(dfs_ocr_all)
            multiplot_performance_noise(
                df_ocr_all, stats_dir, plots_dir, metric=metric, suffix=suffix
            )


def multiplot_performance_time(
    df: pd.DataFrame, stats_dir: str, plots_dir: str, metric="F1", suffix=""
):

    plt.close()

    # plot
    sns.despine()
    sns.set(font_scale=1.4)
    sns.set_style("ticks")

    order = [
        "French",
        "German",
    ]

    line_style = {
        "linestyle": [
            "solid",
            "dotted",
            "dashed",
            "dashdot",
            (0, (5, 5)),
            (0, (3, 1, 1, 1, 1, 1)),
            (0, (3, 5, 1, 5)),
            (0, (1, 1)),
            (0, (5, 1)),
            (0, (3, 5, 1, 5, 1, 5)),
        ]
    }

    g = sns.FacetGrid(
        data=df,
        row="task",
        col="lang",
        hue="system",
        hue_kws=line_style,
        sharey=False,
        sharex=False,
        col_order=order,
        legend_out=True,
        height=5,
        aspect=1.2,
        palette="dark",
    )
    g = g.map(plt.plot, "time_start", metric,)

    g.add_legend(borderaxespad=0)
    g.set_axis_labels(
        "", f"{metric}-score",
    )
    g.set(ylim=(0, 1), yticks=[x / 10 for x in range(0, 11)])
    g.set_titles("{col_name} | {row_name} ")
    g.set_xticklabels(rotation=45)
    g._legend.set_title("")

    g.fig.subplots_adjust(wspace=0.2, hspace=0.4)

    # cut y-axis for NERC
    # axes = g.axes
    # axes[0,0].set_ylim(0.5,1.0)
    # axes[0,1].set_ylim(0.5,1.0)

    # axes[1,0].set_ylim(0.0,1.0)
    # axes[1,1].set_ylim(0.0,1.0)

    # export plot
    fname = f"performance_time_{suffix}_{metric}"
    g.savefig(os.path.join(plots_dir, f"{fname}.png"), dpi=300)

    # export as table
    df.to_csv(os.path.join(stats_dir, f"{fname}.csv"))

    return g


def plot_facet_diachronic(input_dir: str, output_dir: str):

    stats_dir = output_dir
    plots_dir = os.path.join(stats_dir, "plots")

    os.makedirs(plots_dir, exist_ok=True)

    dfs_time_all = []

    for task in [
        "nerc",
        "nel_relaxed_@1",
    ]:

        for metric in ["F1"]:  # 'R', 'P'

            languages = [
                "de",
                "fr",
            ]

            for lang in languages:

                # set ranking file
                if task == "nerc":
                    ranking_file = f"ranking-{lang}-coarse-micro-fuzzy-all.tsv"
                elif "relaxed" in task:
                    ranking_file = f'ranking-{lang}-{task.split("_")[0]}-micro-fuzzy-relaxed.tsv'
                else:
                    ranking_file = f'ranking-{lang}-{task.split("_")[0]}-micro-fuzzy.tsv'

                df = read_ranking(ranking_file, input_dir)

                df = define_sytem_label(df)

                # select particular cutoff for NEL
                if "nel" in task:
                    cutoff = task.split("_")[-1]
                    df = df[df.Evaluation.str.contains(cutoff)]

                df = extend_dataframe(df, lang)
                df_time = get_performance_time(df, n_best_systems=5, n_best_per_team=1)

                regimen = df.Evaluation.str.replace(
                    ".*(LIT-micro-fuzzy).*-TIME.*LED.*(-@.)?", r"\1\2"
                ).unique()
                assert len(regimen) == 1

                suffix = f"{lang}-{task}-{regimen[0]}".upper().replace("_", "-")

                df_time["task"] = (
                    task.upper()
                    if task == "nerc"
                    else task.replace("nel_relaxed_@1", "end-to-end EL")
                )
                dfs_time_all.append(df_time)

    # plot all language together
    suffix = f"all-lang-nel-nerc-{regimen[0]}".upper().replace("_", "-")

    df_time_all = pd.concat(dfs_time_all)
    multiplot_performance_time(df_time_all, stats_dir, plots_dir, metric=metric, suffix=suffix)


def main(args):

    input_dir = args["--input-dir"]
    output_dir = args["--output-dir"]
    log_file = args["--log-file"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    logging.info(f"Producing plots from rankings files in {input_dir}")
    plot_all_languages_noise_diachronic(input_dir, output_dir)
    plot_facet_diachronic(input_dir, output_dir)

    logging.info(f"Plots saved to {output_dir}")


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
