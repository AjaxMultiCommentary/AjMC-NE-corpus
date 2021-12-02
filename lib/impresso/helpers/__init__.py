import os
import logging
import glob
import re
import pandas as pd
from typing import NamedTuple

from stringdist import levenshtein_norm


HYPHENS = ["-", "¬"]
PATTERN_HYPHEN_CLEANING = re.compile(fr'[{"".join(HYPHENS)}]\s*')

LOGGER = logging.getLogger(__name__)


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


ImpressoDocument = NamedTuple(
    "ImpressoDocument",
    [
        ("newspaper", str),
        ("date", str),
        ("id", str),
        ("filename", str),
        ("filepath", str),
        ("segments", dict),
        ("mentions", dict),
        ("links", list),
        ("relations", list),
        ("text", str),
    ],
)


def compute_levenshtein_distance(surface: str, transcript: str) -> int:
    """Compute the normalized Levensthein distance between two strings after cleaning

    :param str surface: a reference string.
    :param str transcript: a candidate string.
    :return: Levensthein distance
    :rtype: int

    """

    def clean(text: str) -> str:
        """
        Remove the symbols "-" or "¬" together with potential whitespace which may follow
        """
        return PATTERN_HYPHEN_CLEANING.sub("", text,)

    return levenshtein_norm(clean(surface), clean(transcript))


def clean_directory(path: str):
    files = glob.glob(f"{os.path.join(path, '*')}")
    for f in files:
        os.remove(f)
