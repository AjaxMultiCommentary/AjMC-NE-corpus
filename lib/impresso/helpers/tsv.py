import os
import io
from typing import Set, List, Union, NamedTuple

COL_LABELS = [
    "TOKEN",
    "NE-COARSE-LIT",
    "NE-COARSE-METO",
    "NE-FINE-LIT",
    "NE-FINE-METO",
    "NE-FINE-COMP",
    "NE-NESTED",
    "NEL-LIT",
    "NEL-METO",
    "MISC",
]


class TSVComment(NamedTuple):
    n: int
    field: str
    value: str

    def __repr__(self):
        return f"# {self.field} = {self.value}"


class TSVAnnotation(NamedTuple):
    n: int
    token: str
    ne_coarse_lit: str
    ne_coarse_meto: str
    ne_fine_lit: str
    ne_fine_meto: str
    ne_fine_comp: str
    ne_nested: str
    nel_lit: str
    nel_meto: str
    misc: str

    def __repr__(self):
        return (
            f"{self.token}\t{self.ne_coarse_lit}\t"
            f"{self.ne_coarse_meto}\t{self.ne_fine_lit}\t"
            f"{self.ne_fine_meto}\t{self.ne_fine_comp}\t{self.ne_nested}\t"
            f"{self.nel_lit}\t{self.nel_meto}\t{self.misc}"
        )


TSVLine = Union[TSVAnnotation, TSVComment]


def find_datasets_files(base_dir: str) -> List[str]:
    """Finds recursively TSV file in a folder.

    ..note::
        The expected folder structure is one sub-folder per language.

    :param str base_dir: Description of parameter `base_dir`.
    :return: A list of TSV file paths.
    :rtype: List[str]

    """
    datasets_files = []
    for lang in os.listdir(base_dir):
        for file in os.listdir(os.path.join(base_dir, lang)):
            if ".tsv" in file and "orig" not in file:
                datasets_files.append(os.path.join(base_dir, lang, file))
    return datasets_files


def find_missing_iiif_links(input_tsv_file: str) -> Set[str]:
    """Finds which content items don't have IIIF links.

    :param str input_tsv_file: Input TSV file in HIPE format.
    :return: A set of content item IDs which don't have IIIF links.
    :rtype: Set[str]

    """

    missing_links = set()
    with open(input_tsv_file, "r") as f:

        doc_sections = f.read().split("\n\n")

        for doc in doc_sections:
            doc_id = [
                line.strip().split("=")[-1].strip()
                for line in doc.split("\n")
                if "document_id" in line
            ][0]

            iiif_link = [
                line.strip().split("=")[-1].strip()
                for line in doc.split("\n")
                if "segment_iiif_link" in line
            ][0]

            if iiif_link == "_":
                missing_links.add(doc_id)

    return missing_links


def is_tsv_complete(dataset_path: str, expected_doc_ids: List[str]) -> bool:

    with open(dataset_path, "r") as f:
        tsv_doc_ids = [
            line.strip().split("=")[-1].strip()
            for line in f.readlines()
            if line.startswith("#") and "document_id" in line
        ]

    difference = set(expected_doc_ids).difference(set(tsv_doc_ids))

    try:
        assert difference == set()
        return True
    except AssertionError:
        print(f"Following documents are missing from {dataset_path}: {difference}")
        return False


def is_comment(line: str) -> bool:
    return line.startswith("#") and "=" in line


def parse_comment(comment_line: str, line_number: int) -> TSVComment:
    """Parses a line of TSV file into a `TSVComment` object.

    :param str comment_line: Description of parameter `comment_line`.
    :param int line_number: Description of parameter `line_number`.
    :return: Description of returned object.
    :rtype: TSVComment

    """
    try:
        key, value = [
            value.strip() for value in comment_line.replace("#", "").split("=")
        ]
    except:
        import ipdb

        ipdb.set_trace()
    return TSVComment(n=line_number, field=key, value=value)


def parse_annotation(line: str, line_number: int) -> TSVAnnotation:
    """Parses a TSV line into a `TSVAnnotation` object."""
    values = line.split("\t")
    return TSVAnnotation(
        n=line_number,
        token=values[0],
        ne_coarse_lit=values[1] if len(values) >= 2 else None,
        ne_coarse_meto=values[2]  if len(values) >= 3 else None,
        ne_fine_lit=values[3]  if len(values) >= 4 else None,
        ne_fine_meto=values[4]  if len(values) >= 5 else None,
        ne_fine_comp=values[5]  if len(values) >= 6 else None,
        ne_nested=values[6]  if len(values) >= 7 else None,
        nel_lit=values[7]  if len(values) >= 8 else None,
        nel_meto=values[8]  if len(values) >= 9 else None,
        misc=values[9]  if len(values) >= 10 else None,
    )


def parse_tsv(
    file_path: str, mask_nerc: bool = False, mask_nel: bool = False
) -> List[List[TSVLine]]:

    with open(file_path) as f:
        documents = [
            [
                parse_tsv_line(line, line_number, mask_nerc, mask_nel)
                for line_number, line in enumerate(document.split("\n"))
                if not line.startswith("TOKEN") and line != ""
            ]
            for document in f.read().split("\n\n")
        ]
    return documents


def parse_tsv_line(
    line: str, line_number: int, mask_nerc: bool = False, mask_nel: bool = False
) -> TSVLine:
    if is_comment(line):
        return parse_comment(line, line_number)
    else:
        ann = parse_annotation(line, line_number)
        if mask_nerc and mask_nel:
            return mask_all_groundtruth(ann)
        elif mask_nel and not mask_nerc:
            return mask_nel_groundtruth(ann)
        else:
            return ann


def mask_all_groundtruth(annotation: TSVAnnotation, mask: str = "_") -> TSVAnnotation:
    """Hides annotations from an input annotation.

    This is used when preparing the test data for the shared task competition.
    Only neutral fields are kept (`token` and `misc`), while all the rest is
    replaced with the `mask` character
    """
    masked_annotation = TSVAnnotation(
        n=annotation.n,
        token=annotation.token,
        ne_coarse_lit=mask,
        ne_coarse_meto=mask,
        ne_fine_lit=mask,
        ne_fine_meto=mask,
        ne_fine_comp=mask,
        ne_nested=mask,
        nel_lit=mask,
        nel_meto=mask,
        misc=annotation.misc,
    )
    return masked_annotation


def mask_nel_groundtruth(annotation: TSVAnnotation, mask: str = "_") -> TSVAnnotation:
    """Hides only NEL annotations from an input annotation.

    This is used when preparing the test data for bundle 5 of the shared task competition.
    Only NERC-related + neutral fields are kept (`token` and `misc`), while all the rest is
    replaced with the `mask` character.
    """
    masked_annotation = TSVAnnotation(
        n=annotation.n,
        token=annotation.token,
        ne_coarse_lit=annotation.ne_coarse_lit,
        ne_coarse_meto=annotation.ne_coarse_meto,
        ne_fine_lit=annotation.ne_fine_lit,
        ne_fine_meto=annotation.ne_fine_meto,
        ne_fine_comp=annotation.ne_fine_comp,
        ne_nested=mask,
        nel_lit=mask,
        nel_meto=mask,
        misc=annotation.misc,
    )
    return masked_annotation


def write_tsv(documents: List[List[TSVLine]], output_path: str) -> None:
    headers = COL_LABELS
    raw_csv = "\n\n".join(
        ["\n".join([str(line) for line in document]) for document in documents]
    )
    headers_line = "\t".join(headers)
    csv_content = f"{headers_line}\n{raw_csv}"

    with io.open(output_path, "w", encoding="utf-8") as f:
        f.write(csv_content)
