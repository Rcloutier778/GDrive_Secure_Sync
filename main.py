

import argparse
import json
import logging
import os
import os.path
import sys
from collections import defaultdict

import httplib2
import networkx as nx
import pyminizip
from apiclient import discovery
from apiclient.http import MediaFileUpload
from cryptography.fernet import Fernet
from oauth2client.service_account import ServiceAccountCredentials

SCOPES = ['https://www.googleapis.com/auth/drive']

SERVICE_JSON = 'service_account.json'

auth_url="https://accounts.google.com/o/oauth2/v2/auth"

logger = logging.getLogger('GDrive_Secure_Sync')

COMPRESS_LEVEL = 1 # 1-9 zip compression level

API_KEY = ''

TOP_LEVEL_DIR = None

REMOTE_BACKUPS_DIR = ''

DRIVE_ID = ''

FERNET_KEY : str = None # Used to obfuscate folder / filenames in google drive. Generated.
#It's not the end of the world if you loose your key, you'll just need to figure out what's what in remote.


PW = '' # Password used to lock uploaded files in google drive. User provided.

def get_remote_hash(dir, file):
    #TODO
    path = os.path.join(dir, file)
    return 0

def _upload_to_remote(lpath, zip_path):
    #TODO
    return

def upload(path, hashed, pw):
    obj_path, ext = os.path.splitext(path)
    zip_path = '%s.zip' % obj_path
    pyminizip.compress(path, zip_path, pw, COMPRESS_LEVEL)
    
    
    os.remove(zip_path)
    
def local_hash(path):
    return hash(path) % ((sys.maxsize + 1) * 2)

def encrypt(message: str):
    if not isinstance(message, bytes):
        message = message.encode()
    assert FERNET_KEY is not None
    return Fernet(FERNET_KEY).encrypt(message)

def decrypt(token: bytes):
    if not isinstance(token, bytes):
        message = token.decode()
    assert FERNET_KEY is not None
    return Fernet(FERNET_KEY).decrypt(token)


def main():
    print("Good god just use RClone")
    return
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', '--dir', help='Top level directory')
    parser.add_argument('--pw', '--pw', help='Password to use for zip')
    parser.add_argument('--backup_dir', '--backup_dir', help='Where in remote to store backups')
    args = parser.parse_args()

    global PW
    PW = args.pw or ''

    assert os.path.exists(args.dir)
    with open('secret.json', 'r') as f:
        secrets = json.loads(f.read())
        if 'fernet_key' not in secrets:
            secrets['fernet_key'] = Fernet.generate_key()
            
    global FERNET_KEY
    FERNET_KEY = secrets['fernet_key']
    
    global TOP_LEVEL_DIR
    TOP_LEVEL_DIR = args.dir.strip(os.sep).rsplit(os.sep, 1)[0].strip(os.sep)

    global REMOTE_BACKUPS_DIR
    REMOTE_BACKUPS_DIR = args.backup_dir.strip(os.sep)

    global DRIVE_ID
    DRIVE_ID = secrets['drive_id']

    service = get_service()
    
    service.files().emptyTrash()

    res = {}
    for dir, sub_dirs, files in os.walk(args.dir):
        for file in files:
            path = os.path.join(dir, file)
            hashed = local_hash(path)
            if hashed != get_remote_hash(path, file):
                res[path] = hashed


    logger.info('%d files', len(res))
    
    for path in set(path.rsplit(os.sep, 1)[0] for path in res):
        print(path)
        createNewFolder(service=service, name=path)
    
    
    return
    #TODO
    for path, hashed in res.items():
        upload(path, hashed, pw)


def callback(request_id, response, exception):
    if exception:
        # Handle error
        print(exception)
    else:
        print("Permission Id: %s" % response.get('id'))



    
def uploadFileToFolder(service, folderID, fileName):
    """Uploads the file to the specified folder id on the said Google Drive
    Returns:
            fileID, A string of the ID from the uploaded file
    """
    file_metadata = None
    if folderID is None:
        file_metadata = {
            'name' : fileName
        }
    else:
        file_metadata = {
            'name' : fileName,
            'parents': [ folderID ]
        }
    
    media = MediaFileUpload(fileName, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='name,id', supportsAllDrives=True).execute()
    
    return file.get('id')

def get_remote_file_tree(service):
    "Full folder path -> files"
    G, id_to_name = get_remote_tree_nx(service)

    tree = defaultdict(set)
    def recr_tree(n, path):
        for s in G.successors(n):
            if list(G.successors(s)):
                recr_tree(s, os.path.join(path, id_to_name[s]))
            else:
                tree[path].add(id_to_name[s])
        
    recr_tree(DRIVE_ID, '')
    tree = dict(tree)
    return tree

def get_remote_tree(service):
    "Dict representation of parent -> child"
    G, id_to_name = get_remote_tree_nx(service)

    def recr_tree(n):
        tmp = {}
        for s in G.successors(n):
            tmp[id_to_name[s]] = recr_tree(s)
    
        return tmp

    tree = {'root':recr_tree(DRIVE_ID)}

    return tree

def get_remote_tree_nx(service):
    "Gets the remote tree as an networkx DiGraph"
    results = service.files().list(q="", pageSize=10, fields="files(id, name, parents)", driveId=DRIVE_ID, includeItemsFromAllDrives=True, corpora='drive', supportsAllDrives=True).execute()
    
    # Overkill but I don't care cause easier
    
    G = nx.DiGraph()
    
    id_to_name = {DRIVE_ID:'root'}
    
    tree = defaultdict(dict)
    
    for f in results['files']:
        id_to_name[f['id']] = decrypt(f['name'])
        G.add_node(f['id'])
        G.add_node(f['parents'][0])
        G.add_edge(f['parents'][0], f['id'])
        
    
    return G, id_to_name


def getObjFromPath(service, path):
    files = service.files().get(q='name=%s' % encrypt(path), fields="files(id, name, parents)", supportsAllDrives=True, corpora='drive', driveId=DRIVE_ID, includeItemsFromAllDrives=True).execute()['files']
    
    return files[0] if files else None

def _createNewFolder(service, parent_dir, current_dir, path):
    folder = getObjFromPath(service=service, path=path)
    if folder is not None:
        return folder
    folder_metadata = {
        'name': encrypt(path),
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [] if parent_dir is None else [getObjFromPath(service, parent_dir)['Id']],
    }
    folder = service.files().create(body=folder_metadata, supportsAllDrives=True).execute()
    return folder

def createNewFolder(service, name):
    """Will create a new folder in the root of the supplied GDrive
    Returns:
        The new folder ID, or the id of the already existing folder
    """
    # replace local top level dir with remote
    name = name.replace(TOP_LEVEL_DIR, REMOTE_BACKUPS_DIR, 1)
    
    splitpath = name.split(os.sep)
    folder = {}
    for index in range(len(splitpath)):
        current_dir = splitpath[index]
        parent_dir = None if index == 0 else splitpath[index-1]
        print('%s/%s' % (parent_dir, current_dir,))

        folder = _createNewFolder(service, parent_dir, current_dir)

    return folder.get('id')

def get_service():
    """Get a service that communicates to a Google API.
    Returns:
      A service that is connected to the specified API.
    """
    print("Acquiring credentials...")
    credentials = ServiceAccountCredentials.from_json_keyfile_name(filename=SERVICE_JSON, scopes=SCOPES)
    
    #Has to check the credentials with the Google servers
    print("Authorizing...")
    http = credentials.authorize(httplib2.Http())
    
    # Build the service object for use with any API
    print("Acquiring service...")
    service = discovery.build(serviceName="drive", version="v3", credentials=credentials )
    
    print("Service acquired!")
    return service

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

