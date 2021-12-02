"""
Script to produce the official ranking summary tables for the HIPE shared task.

Usage:
    lib/format_rankings_summary.py --input-dir=<id> --output-dir=<od> [--log-file=<log>]
"""  # noqa


import os
import logging
from docopt import docopt
import pandas as pd
import numpy as np
from tabulate import tabulate

PROLOGUE = """
We provide an **overview table** of the anonymized results of the runs submitted by 13 teams for the **first and second** phases.

- Date: 09.06.2020.
- Bundles: 1 to 5
- Detailed results for all systems can be found in this .tsv file.
- Detailed results for each team's runs are sent privately.
- System name composition is: teamID_bundle_lang_run.
- F1 scores of 0.0 are excluded from the table.
- Results are ordered by F scores.
- Results will be de-anonymized on Fri 12 June.

### About the evaluation (reminder)

- NERC and Entity Linking (EL) are evaluated in terms of macro and micro Precision, Recall, F1-measure. Here only micro is reported.

- Evaluation scenarios for **NERC**
       - **Strict**: exact boundary matching.
       - **Fuzzy**: fuzzy (=overlap) boundary matching.

- Evaluation scenarios for **EL**:
In terms of boundaries, NEL is only evaluated according to fuzzy boundary matching in all scenarios. What is of interest is the capacity to provide the correct link rather than the correct boundaries (NERC task).
         - **Strict**: The system's top link prediction (NIL or QID) must be identical with the gold standard annotation.
        - **Relaxed**: The set of system's predictions is expanded with a set of historically related entities QIDs, e.g "Germany" is expended with the more specific "Confederation of the Rhine" and both are considered as valid answers. Systems are therefore evaluated more generously.  For this scenario, we additionally report F@1/3/5 in the .tsv files.

"""


def read_ranking(ranking_name: str, rankings_dir: str) -> pd.DataFrame:
    relevant_tsv_files = [
        os.path.join(rankings_dir, file)
        for file in os.listdir(rankings_dir)
        if ranking_name in file
    ][0]

    df = pd.read_csv(relevant_tsv_files, delimiter="\t")

    selected_cols = [
        "Evaluation",
        "Label",
        "F1",
        "P",
        "R",
        #'run',
        #'F1_std','P_std', 'R_std', 'TP', 'FP','FN',
        "System",
    ]
    # print something
    df = df[~(df.F1 == 0.0)]
    # return df.reset_index()[selected_cols]
    return df[selected_cols]


def filter_ranking(ranking_df: pd.DataFrame, evaluation: str) -> pd.DataFrame:
    return ranking_df.copy()[
        ranking_df.Evaluation.str.contains(evaluation) & (ranking_df.Label == "ALL")
    ]


def compile_rankings_summary(rankings_dir: str) -> str:

    # take only micro scores

    summary = ""

    languages = [("de", "German"), ("en", "English"), ("fr", "French")]

    h = ["Rank", "System", "F1", "Precision", "Recall"]

    scenarios = [
        {
            "desc": "Relevant bundles: 1-4",
            "id": "nerc-coarse",
            "label": "NERC coarse",
            "measures": [
                (
                    "strict",
                    "NE-COARSE-LIT-micro-strict-TIME-ALL-LED-ALL",
                    "strict (literal sense)",
                ),
                (
                    "fuzzy",
                    "NE-COARSE-LIT-micro-fuzzy-TIME-ALL-LED-ALL",
                    "fuzzy (literal sense)",
                ),
                (
                    "strict",
                    "NE-COARSE-METO-micro-strict-TIME-ALL-LED-ALL",
                    "strict (metonymic sense)",
                ),
                (
                    "fuzzy",
                    "NE-COARSE-METO-micro-fuzzy-TIME-ALL-LED-ALL",
                    "fuzzy (metonymic sense)",
                ),
            ],
        },
        {
            "desc": "Relevant bundles: 1, 3",
            "id": "nerc-fine",
            "label": "NERC fine",
            "measures": [
                (
                    "strict",
                    "NE-FINE-LIT-micro-strict-TIME-ALL-LED-ALL",
                    "strict (literal sense)",
                ),
                (
                    "fuzzy",
                    "NE-FINE-LIT-micro-fuzzy-TIME-ALL-LED-ALL",
                    "fuzzy (literal sense)",
                ),
                (
                    "strict",
                    "NE-FINE-METO-micro-strict-TIME-ALL-LED-ALL",
                    "strict (metonymic sense)",
                ),
                (
                    "fuzzy",
                    "NE-FINE-METO-micro-fuzzy-TIME-ALL-LED-ALL",
                    "fuzzy (metonymic sense)",
                ),
                (
                    "strict",
                    "NE-COMP-micro-strict-TIME-ALL-LED-ALL",
                    "strict NE components",
                ),
                (
                    "fuzzy",
                    "NE-COMP-micro-fuzzy-TIME-ALL-LED-ALL",
                    "fuzzy NE components",
                ),
                (
                    "strict",
                    "NE-NESTED-micro-strict-TIME-ALL-LED-ALL",
                    "strict, nested entities",
                ),
                (
                    "fuzzy",
                    "NE-NESTED-micro-fuzzy-TIME-ALL-LED-ALL",
                    "fuzzy, nested entities",
                ),
            ],
        },
        {
            "desc": "Relevant bundles: 1, 2",
            "id": "el",
            "label": "EL",
            "measures": [
                (
                    "strict",
                    "LIT-micro-fuzzy-TIME-ALL-LED-ALL-@1",
                    "strict @1 (literal sense)",
                ),
                (
                    "strict",
                    "METO-micro-fuzzy-TIME-ALL-LED-ALL-@1",
                    "strict @1 (metonymic sense)",
                ),
                (
                    "relaxed",
                    "LIT-micro-fuzzy-relaxed-TIME-ALL-LED-ALL-@1",
                    "relaxed @1 (literal sense)",
                ),
                (
                    "relaxed",
                    "METO-micro-fuzzy-relaxed-TIME-ALL-LED-ALL-@1",
                    "relaxed @1 (metonymic sense)",
                ),
            ],
        },
        {
            "desc": "Relevant bundles: 5",
            "id": "el-only",
            "label": "EL only",
            "measures": [
                (
                    "strict",
                    "LIT-micro-fuzzy-TIME-ALL-LED-ALL-@1",
                    "strict @1 (literal sense)",
                ),
                (
                    "strict",
                    "METO-micro-fuzzy-TIME-ALL-LED-ALL-@1",
                    "strict @1 (metonymic sense)",
                ),
                (
                    "relaxed",
                    "LIT-micro-fuzzy-relaxed-TIME-ALL-LED-ALL-@1",
                    "relaxed @1 (literal sense)",
                ),
                (
                    "relaxed",
                    "METO-micro-fuzzy-relaxed-TIME-ALL-LED-ALL-@1",
                    "relaxed @1 (metonymic sense)",
                ),
            ],
        },
    ]

    summary += "# CLEF HIPE 2020 preliminary results\n"
    summary += PROLOGUE
    summary += "\n\n<!--ts-->\n<!--te-->\n"

    for scenario in scenarios:
        desc = scenario["desc"]
        scenario_id = scenario["id"]
        label = scenario["label"]
        measures = scenario["measures"]
        summary += f"\n\n## {label}\n\n{desc}"

        for lang_id, lang_label in languages:

            for measure, eval_level, measure_label in measures:

                if scenario_id == "nerc-coarse":
                    try:
                        ranking_filename = (
                            f"ranking-{lang_id}-coarse-micro-{measure}-all.tsv"
                        )
                        ranking_df = read_ranking(ranking_filename, rankings_dir)
                    except:
                        # print(f"{ranking_filename} not found")
                        pass

                elif scenario_id == "nerc-fine":

                    if lang_id == "en":
                        continue

                    try:
                        ranking_filename = (
                            f"ranking-{lang_id}-fine-micro-{measure}-all.tsv"
                        )
                        ranking_df = read_ranking(ranking_filename, rankings_dir)
                    except:
                        # print(f"{ranking_filename} not found")
                        pass

                elif scenario_id == "el":
                    try:
                        if measure == "relaxed":
                            ranking_filename = (
                                f"ranking-{lang_id}-nel-micro-fuzzy-{measure}.tsv"
                            )
                        else:
                            # it's strict but no strict in the filename
                            ranking_filename = f"ranking-{lang_id}-nel-micro-fuzzy.tsv"
                        ranking_df = read_ranking(ranking_filename, rankings_dir)
                    except:
                        # print(f"{ranking_filename} not found")
                        pass

                elif scenario_id == "el-only":
                    try:
                        if measure == "relaxed":
                            ranking_filename = (
                                f"ranking-{lang_id}-nel-only-micro-fuzzy-{measure}.tsv"
                            )
                        else:
                            # it's strict but no strict in the filename
                            ranking_filename = (
                                f"ranking-{lang_id}-nel-only-micro-fuzzy.tsv"
                            )
                        ranking_df = read_ranking(ranking_filename, rankings_dir)
                    except:
                        # print(f"{ranking_filename} not found")
                        pass

                filter_ranking_df = filter_ranking(ranking_df, eval_level)
                filter_ranking_df["Rank"] = [
                    n + 1 for n, row in enumerate(filter_ranking_df.iterrows())
                ]
                filter_ranking_df = filter_ranking_df.set_index("Rank")
                eval_key = list(filter_ranking_df.Evaluation.unique())[0]
                summary += (
                    f"\n\n### {label} {lang_label} {measure_label} \[`{eval_key}`\]\n\n"
                )
                summary += tabulate(
                    filter_ranking_df[["System", "F1", "P", "R"]],
                    headers=h,
                    tablefmt="pipe",
                    numalign="left",
                )

    summary += "\n"
    return summary


def main(args):
    log_file = args["--log-file"]
    input_dir = args["--input-dir"]
    output_dir = args["--output-dir"]

    logging.basicConfig(
        filename=log_file,
        filemode="w",
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    md_summary_path = os.path.join(input_dir, "ranking_summary.md")
    md_summary = compile_rankings_summary(input_dir)
    with open(md_summary_path, "w") as f:
        f.write(md_summary)


if __name__ == "__main__":
    arguments = docopt(__doc__)
    main(arguments)
