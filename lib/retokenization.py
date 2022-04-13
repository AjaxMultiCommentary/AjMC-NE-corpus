"""
Retokenize UIMA CAS XMI data and save in the original format.
"""

import ipdb
import sys
from tqdm import tqdm
from typing import List
import argparse
import logging
from pathlib import Path
import csv
from collections import OrderedDict
import pandas as pd
from cassis import load_cas_from_xmi, load_typesystem

from unicodedata import category

sys.path.append("../")
sys.path.append("../../")
from ajmc_utils import HYPHENS

def parse_args():
    """Parse the arguments given with program call"""

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i",
        "--dir_in",
        required=True,
        action="store",
        dest="dir_in",
        help="name of input dir where the xmi files are stored",
    )

    parser.add_argument(
        "-s",
        "--schema",
        required=True,
        action="store",
        dest="f_schema",
        help="path to the xml schema file",
    )

    parser.add_argument(
        "-l",
        "--log",
        action="store",
        default="clef_retokenization.log",
        dest="f_log",
        help="name of log file",
    )

    parser.add_argument(
        "-o",
        "--dir_out",
        required=True,
        action="store",
        dest="dir_out",
        help="name of the output dir where the tsv files are stored",
    )

    return parser.parse_args()


class Retokenizer:
    def __init__(self, xmi: str, xml: str):
        """ Change token annotations

        :param str xmi: path to existing xmi annotation file.
        :param str xml: path to xml schema file.
        :return: None
        :rtype: None

        """

        self.xmi = xmi
        self.xml = xml

        self.typesystem = None
        self.cas = None

        self.tokenType = "de.tudarmstadt.ukp.dkpro.core.api.segmentation.type.Token"

    def retokenize(self):
        """Retokenize the document.

        Perform splitting off of apostrophes and hyphens from tokens into new tokens
        and remove tokens with unprintable characters.
        """

        with open(self.xml, "rb") as f:
            self.typesystem = load_typesystem(f)

        with open(self.xmi, "rb") as f:
            self.cas = load_cas_from_xmi(f, typesystem=self.typesystem)

        self.split_off_spaces()
        self.split_off_apostrophes()
        self.split_off_parenthesis()
        self.split_off_hyphens()
        self.split_off_punctuation()
        self.remove_unprintable_tokens()
        self.remove_empty_tokens()

    def split_off_spaces(self):
        """
        Split off spaces when present in a token

        Example:
        TODO add example
        """

        cas = self.cas
        tokenType = self.tokenType
        splitting_sign = " "

        tokens = []
        for tok in cas.select(tokenType):
            tok_text = tok.get_covered_text()
            if splitting_sign in tok_text and len(tok_text) > 1:
                tokens += self.splitting_at_symbol(tok, splitting_sign)
                #ipdb.set_trace()
        cas.add_all(tokens)

    def split_off_apostrophes(self):
        """
        Split off apostrophes when glued together with token

        Example:
        2020-02-17 10:20:28,567 - root - INFO - Token 'Finanz-Budger's' was tokenized into ['Finanz-Budger', "'", 's']
        """

        cas = self.cas
        tokenType = self.tokenType

        tokens = []
        for tok in cas.select(tokenType):
            tok_text = tok.get_covered_text()
            if "'" in tok_text and len(tok_text) > 1:
                tokens += self.splitting_at_symbol(tok, "'")
        cas.add_all(tokens)

        tokens = []
        for tok in cas.select(tokenType):
            tok_text = tok.get_covered_text()
            if "’" in tok_text and len(tok_text) > 1:
                tokens += self.splitting_at_symbol(tok, "’")
        cas.add_all(tokens)

    def split_off_parenthesis(self):
        """
        Split off apostrophes when glued together with token
        Example:
        2022-03-15 11:36:27,908 - root - INFO - Token '(Martin' was tokenized into ['(', 'Martin']
        
        """

        cas = self.cas
        tokenType = self.tokenType

        splitting_signs = [
            "(",
            ")",
            "[",
            "]",
            "{",
            "}"
        ]

        for splitting_sign in splitting_signs:
            tokens = []
            for tok in cas.select(tokenType):
                tok_text = tok.get_covered_text()
                if splitting_sign in tok_text and len(tok_text) > 1:
                    tokens += self.splitting_at_symbol(tok, splitting_sign)
            cas.add_all(tokens)

    def split_off_hyphens(self):
        """
        Split off hyphens when glued together with token

        Example:
        2020-02-17 10:20:28,568 - root - INFO - Token 'Finanz-Budger' was tokenized into ['Finanz', '-', 'Budger']
        """

        cas = self.cas
        tokenType = self.tokenType

        splitting_signs = [
            "-",
            "—"
        ]
        for splitting_sign in splitting_signs:
            tokens = []
            for tok in cas.select(tokenType):
                tok_text = tok.get_covered_text()
                if splitting_sign in tok_text and len(tok_text) > 1:
                    tokens += self.splitting_at_symbol(tok, splitting_sign)
            cas.add_all(tokens)

    def split_off_punctuation(self):
        """
        Split off punctuation when glued together with token

        Example:
        2022-03-15 11:26:16,585 - root - INFO - Token 'Chevaliers,' was tokenized into ['Chevaliers', ',']
        2022-03-15 11:26:16,767 - root - INFO - Token 'σιωπῇ.' was tokenized into ['σιωπῇ', '.']
        """

        cas = self.cas
        tokenType = self.tokenType

        splitting_signs = [
            ".",
            ",",
            ":",
            ";",
            "=",
            "͵",
            "„",
            "“",
            "‚",
            "?",
            "”"
        ]

        for splitting_sign in splitting_signs:
            tokens = []
            for tok in cas.select(tokenType):
                tok_text = tok.get_covered_text()
                if splitting_sign in tok_text and len(tok_text) > 1:
                    tokens += self.splitting_at_symbol(tok, splitting_sign)
            cas.add_all(tokens)

    def remove_unprintable_tokens(self):
        """
        Remove annotations of tokens that contain non-printable characters.

        Non-printable characters are Unicode control sequences which may cause
        problems when processing further. Non-printable characters are replaced
        with an underscore in the original text.
        """

        cas = self.cas
        tokenType = self.tokenType

        remove_tokens = []

        for i, tok in enumerate(cas.select(tokenType)):
            tok_text = tok.get_covered_text()
            tok_clean = "".join(ch for ch in tok_text if category(ch)[0] != "C")

            if tok_text != tok_clean:
                logging.info(
                    f"Token '{tok_text}' has unprintable characters and will be removed entirely in document: {self.xmi}."
                )
                remove_tokens.append(i)

        for idx in reversed(remove_tokens):
            del cas._current_view.type_index[tokenType][idx]

        text = cas.sofa_string
        text_clean = "".join(ch if category(ch)[0] != "C" else "_" for ch in text)
        cas.sofa_string = text_clean

        assert len(text) == len(text_clean)

    def remove_empty_tokens(self):
        """
        Remove annotations of tokens that contain non-printable characters.

        Non-printable characters are Unicode control sequences which may cause
        problems when processing further. Non-printable characters are replaced
        with an underscore in the original text.
        """

        cas = self.cas
        tokenType = self.tokenType

        remove_tokens = []

        for i, tok in enumerate(cas.select(tokenType)):
            tok_text = tok.get_covered_text()

            if tok_text == " ":
                logging.info(
                    f"Token '{tok_text}' is a space and will be removed entirely in document: {self.xmi}."
                )
                remove_tokens.append(i)

        for idx in reversed(remove_tokens):
            del cas._current_view.type_index[tokenType][idx]

    def splitting_at_symbol(self, tok, symbol: str):
        """Split a token into its subtokens at a particular symbol (e.g., apostroph).
        A token may yield multiple subtokens.

        :param type tok: Original Token object .
        :param str symbol: Symbol at which token get splitted into subtokens.
        :return: Atomic subtokens equivalent to token when concatenated.
        :rtype: List of Token objects

        """

        Token = self.typesystem.get_type(self.tokenType)

        tokens = []
        tok_text = tok.get_covered_text()
        tok_splits = tok_text.split(symbol)

        # insert splitting symbol at every second position
        i = 1
        while i < len(tok_splits):
            tok_splits.insert(i, symbol)
            i += 2

        # consider the empty string when the splitting symbols
        # occurs at the end of a token (e.g. Alex')
        if not tok_splits[-1]:
            del tok_splits[-1]

        # consider the empty string when the splitting symbols
        # occurs at the beginning of a token (e.g. "(um")
        if not tok_splits[0]:
            del tok_splits[0]

        # redefine the boundary of the first token up to the first split
        split_pos = len(tok_splits[0])
        tok.end = tok.begin + split_pos

        # add new segments for remaining tokens
        # apostrophes are also tokens
        for split in tok_splits[1:]:
            start = tok.begin + split_pos
            end = tok.begin + split_pos + len(split)
            tokens.append(Token(begin=start, end=end))
            split_pos += len(split)

        try:
            assert tok_text == "".join(tok_splits)
            logging.info(
                f"Token '{tok_text}' was tokenized into {tok_splits} in document: {self.xmi}"
            )
        except AssertionError:
            logging.error(
                f"Token '{tok_text}' couldn't be properly tokenized into {tok_splits} in document: {self.xmi}"
            )

        return tokens


def index_inception_files(dir_data, suffix=".xmi") -> list:
    """Index all .xmi files in the provided directory

    :param type dir_data: Path to top-level dir.
    :param type suffix: Only consider files of this type.
    :return: List of found files.
    :rtype: list

    """

    return sorted([path for path in Path(dir_data).rglob("*" + suffix)])


def batch_retokenization(dir_in: str, dir_out: str, f_schema: str):
    """Start a batch retokenization of xmi files in the given folder .

    :param str dir_in: Top-level folder containing the .xmi-files.
    :param str dir_out: Top-level output folder for the converted documents.
    :param str f_schema: Path to the .XML-file of the schema.
    :return: None.
    :rtype: None

    """

    xmi_in_files = index_inception_files(dir_in)
    xmi_out_files = [Path(str(p).replace(dir_in, dir_out)) for p in xmi_in_files]

    msg = f"Start retokenization of {len(xmi_in_files)} files."
    logging.info(msg)
    print(msg)

    for f_xmi_in, f_xmi_out in tqdm(list(zip(xmi_in_files, xmi_out_files))):
        f_xmi_out.parent.mkdir(parents=True, exist_ok=True)
        retokenizer = Retokenizer(f_xmi_in, f_schema)
        retokenizer.retokenize()
        retokenizer.cas.to_xmi(f_xmi_out, pretty_print=True)

    logging.info(f"Retokenization completed.")


def main():

    args = parse_args()

    logging.basicConfig(
        filename=args.f_log,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    batch_retokenization(args.dir_in, args.dir_out, args.f_schema)


################################################################################
if __name__ == "__main__":
    main()
