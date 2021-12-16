#!/usr/bin/env python
# coding: utf-8

# TODO: check if the file is already in the output directory

"""
CLI script to download curated documents from inception.

Usage:
    scripts/download_curated.py --project-name=<pname> --output-dir=<od> [--api-endpoint=<api> --user=<u> --password=<pwd> --name-contains=<name>]
"""

import requests
import zipfile
import io
import os
import sys
sys.path.append('./')
from pathlib import Path
from requests.auth import HTTPBasicAuth
from docopt import docopt
from lib.impresso.helpers.inception import make_inception_client, find_project_by_name

__author__ = "Matteo Romanello"
__email__ = "matteo.romanello@epfl.ch"
__organisation__ = "DH Lab, EPFL"
__status__ = "development"


def fetch_documents(project_id, username, password, api_endpoint):

    req_uri = f'{api_endpoint}projects/{project_id}/documents'
    print(req_uri)
    authentication = HTTPBasicAuth(username, password)
    return requests.get(req_uri, auth=authentication).json()['body']


def download_curated_document(project_id, document_id, username, password, download_path, api_endpoint):
    try:
        Path(download_path).mkdir(parents=True, exist_ok=True)
        req_uri = f'{api_endpoint}projects/{project_id}/documents/{document_id}/curation'
        authentication = HTTPBasicAuth(username, password)
        r = requests.get(req_uri, auth=authentication, stream=True)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        filenames = [f.filename for f in z.filelist]
        print(f"[proj={project_id}, doc={document_id}]", f"Following files were downloaded: {','.join(filenames)}")
        z.extractall(path=download_path)
        return True
    except Exception as e:
        print(e)
        return False


def main(args):

    project_name = args['--project-name']
    user = args['--user'] if  args['--user'] else os.environ['INCEPTION_USERNAME']
    pwd = args['--password'] if args['--password'] else os.environ['INCEPTION_PASSWORD']
    out_dir = args['--output-dir']
    name_filter = args['--name-contains']
    api_endpoint = args['--api-endpoint'] if args['--api-endpoint'] else os.path.join(os.environ['INCEPTION_HOST'], 'api/aero/v1/')

    # find the project id by looking up the project name in inception API
    inception_client = make_inception_client()
    project_id = find_project_by_name(inception_client, project_name).project_id
    print(f"Project {project_name} has ID {project_id}")

    #out_dir = os.path.join(out_dir, project_name)

    for doc in fetch_documents(project_id, user, pwd, api_endpoint):

        if name_filter is not None:
            if name_filter not in doc['name']:
                continue

        if doc['state'] == 'CURATION-COMPLETE':
            print(f"Doc {doc['id']} {doc['name']} is" f"{doc['state']} and will be downloaded")
            success = download_curated_document(project_id, doc['id'], user, pwd, out_dir, api_endpoint)
            assert success


if __name__ == '__main__':
    arguments = docopt(__doc__)
    main(arguments)
