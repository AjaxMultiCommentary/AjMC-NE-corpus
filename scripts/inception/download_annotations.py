#!/usr/bin/env python
# coding: utf-8

# TODO: check if the file is already in the output directory

"""
CLI script to download curated documents from inception.

Usage:
    scripts/download_from_inception.py --user=<u> --password=<pwd> --project-id=<pid> --output-dir=<od> --api-endpoint=<api> --annotator-id=<annid> [--name-contains=<name> --ignore-finished]
"""  # noqa

import os
import requests
import zipfile
import io
from requests.auth import HTTPBasicAuth
from docopt import docopt

__author__ = "Matteo Romanello"
__email__ = "matteo.romanello@epfl.ch"
__organisation__ = "DH Lab, EPFL"
__status__ = "development"


def fetch_documents(project_id, username, password, api_endpoint):

    req_uri = f'{api_endpoint}projects/{project_id}/documents'
    print(req_uri)
    authentication = HTTPBasicAuth(username, password)
    return requests.get(req_uri, auth=authentication).json()['body']


def fetch_annotations(project_id, document_id, username, password, api_endpoint):

    req_uri = (
        f'{api_endpoint}projects/{project_id}/documents/'
        f'{document_id}/annotations'
    )
    authentication = HTTPBasicAuth(username, password)
    return requests.get(req_uri, auth=authentication).json()['body']


def download_document(
    project_id,
    document_id,
    document_name,
    username,
    password,
    download_path,
    api_endpoint
):
    try:
        req_uri = (
            f'{api_endpoint}projects/{project_id}/documents/'
            f'{document_id}'
        )
        params = {'format': 'xmi'}
        authentication = HTTPBasicAuth(username, password)
        req = requests.get(
            req_uri,
            auth=authentication,
            stream=True,
            params=params
        )
        with open(
            f'{os.path.join(download_path, document_name)}',
            'wb'
        ) as outfile:
            outfile.write(req.content)
        return True
    except Exception as e:
        print(e)
        return False


def download_annotated_document(
    project_id,
    document_id,
    annotator_id,
    username,
    password,
    download_path,
    api_endpoint
):
    try:
        req_uri = (
            f'{api_endpoint}projects/{project_id}/documents/'
            f'{document_id}/annotations/{annotator_id}'
        )
        authentication = HTTPBasicAuth(username, password)
        req = requests.get(req_uri, auth=authentication, stream=True)
        z = zipfile.ZipFile(io.BytesIO(req.content))
        filenames = [f.filename for f in z.filelist]
        print(
            f"[proj={project_id}, doc={document_id}]",
            f"Following files were downloaded: {','.join(filenames)}"
        )
        z.extractall(path=download_path)
        return True
    except Exception as e:
        print(e)
        return False


def main(args):

    project_id = args['--project-id']
    user = args['--user']
    pwd = args['--password']
    out_dir = args['--output-dir']
    name_filter = args['--name-contains']
    api_endpoint = args['--api-endpoint']
    annotator_id = args['--annotator-id']
    ignore_finished_docs = args['--ignore-finished']

    for doc in fetch_documents(project_id, user, pwd, api_endpoint):

        should_download = True

        annotations = fetch_annotations(
            project_id,
            doc['id'],
            user,
            pwd,
            api_endpoint
        )

        target_annotations = [
            annotation
            for annotation in annotations
            if annotation['user'] == annotator_id
        ]

        if target_annotations:
            target_annotations = target_annotations[0]
            if target_annotations['state'] == 'COMPLETE':
                print(f"Skipping {doc['name']} as {target_annotations['state']}")
                should_download = False
        else:
            pass

        if should_download:
            print(
                f"Doc {doc['id']} {doc['name']} is"
                f"{doc['state']} and will be downloaded"
            )
            success = download_document(
                project_id,
                doc['id'],
                doc['name'],
                user,
                pwd,
                out_dir,
                api_endpoint
            )
            assert success


if __name__ == '__main__':
    arguments = docopt(__doc__)
    main(arguments)
