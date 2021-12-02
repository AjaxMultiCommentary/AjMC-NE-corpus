import os
import sys
import pandas as pd
from tqdm import tqdm
from typing import List
from cassis import Cas, load_cas_from_xmi, load_typesystem


def find_xmi_files(base_dir: str) -> List[str]:
    """Finds recursively XMI files in a folder.

    ..note::
        The expected folder structure is one sub-folder per language.

    :param str base_dir: Description of parameter `base_dir`.
    :return: A list of XMI file paths.
    :rtype: List[str]

    """
    datasets_files = []
    for lang in os.listdir(base_dir):
        for file in os.listdir(os.path.join(base_dir, lang)):
            if ".xmi" in file:
                datasets_files.append(os.path.join(base_dir, lang, file))
    return datasets_files


def copy_iiif_links(source_xmi: str, target_xmi: str, xmi_schema: str) -> None:
    """Copies IIIF image links from a source XMI file to a target XMI file.

    :param str source_xmi: Description of parameter `source_xmi`.
    :param str target_xmi: Description of parameter `target_xmi`.
    :param str xmi_schema: Description of parameter `xmi_schema`.
    :return: Description of returned object.
    :rtype: None

    """

    imgLinkType = "webanno.custom.ImpressoImages"

    with open(xmi_schema, "rb") as f:
        typesystem = load_typesystem(f)

    with open(source_xmi, "rb") as f:
        source_cas = load_cas_from_xmi(f, typesystem=typesystem)

    with open(target_xmi, "rb") as f:
        target_cas = load_cas_from_xmi(f, typesystem=typesystem)

    ImageLink = typesystem.get_type(imgLinkType)

    for annotation in source_cas.select(imgLinkType):
        target_cas.add_annotation(
            ImageLink(begin=annotation.begin, end=annotation.end, link=annotation.link)
        )
    target_cas.to_xmi(target_xmi, pretty_print=True)


def contains_iiif_links(xmi_file: str, xmi_schema: str) -> bool:
    """Determines whether an XMI file contains IIIF links.

    :param str xmi_file: Description of parameter `xmi_file`.
    :param str xmi_schema: Description of parameter `xmi_schema`.
    :return: Description of returned object.
    :rtype: bool

    """
    imgLinkType = "webanno.custom.ImpressoImages"

    with open(xmi_schema, "rb") as f:
        typesystem = load_typesystem(f)

    with open(xmi_file, "rb") as f:
        cas = load_cas_from_xmi(f, typesystem=typesystem)

    ImageLink = typesystem.get_type(imgLinkType)
    image_links = list(cas.select(imgLinkType))
    return len(image_links) > 0
