

import httplib2
import os
import time
from apiclient import discovery
from apiclient.http import MediaFileUpload
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from oauth2client.service_account import ServiceAccountCredentials
import os
import os.path
import argparse

from collections import defaultdict
import pyminizip
import logging
import requests
import json

import google.oauth2.credentials
import google_auth_oauthlib.flow


SCOPES = 'https://www.googleapis.com/auth/drive'

SERVICE_JSON = 'service_account.json'

auth_url="https://accounts.google.com/o/oauth2/v2/auth"

logger = logging.getLogger('GDrive_Secure_Sync')

COMPRESS_LEVEL = 1 # 1-9

API_KEY = ''


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
    

def main():
    
    
    service = get_service()
    folderID = createNewFolder(service=service,name="test")
    
    return
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', '--dir', help='Top level directory')
    parser.add_argument('--pw', '--pw', help='Password to use for zip')
    args = parser.parse_args()

    pw = args.pw or ''

    assert os.path.exists(args.dir)
    global API_KEY
    API_KEY = json.loads('secret.json')['api-key']
    


    res = {}
    for dir, sub_dirs, files in os.walk(args.dir):
        for file in files:
            path = os.path.join(dir, file)
            hashed = hash(path)
            if hashed != get_remote_hash(path):
                res[path] = hashed


    logger.info('%d files', len(res))
    
    for path, hashed in res.items():
        upload(path, hashed, pw)


def callback(request_id, response, exception):
    if exception:
        # Handle error
        print(exception)
    else:
        print("Permission Id: %s" % response.get('id'))


def getIDfromName(service, name):
    """Gets the first item with the specified name in the Google Drive
    and returns its unique ID
	Returns:
		itemID, the unique ID for said G-Drive item name provided
		None (null value), if file not found
    """
    print("Looking for item with name of: "+name)
    results = service.files().list(q="name='"+name+"'", pageSize=1, fields="files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        print("Item not found...\n")
        return None
    itemID = items[0]['id']
    print("Acquired item id: "+itemID+" for item called: "+items[0]['name']+"\n")
    return itemID
    
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
        print("Uploading file to: "+folderID)
        file_metadata = {
            'name' : fileName,
            'parents': [ folderID ]
        }
    
    media = MediaFileUpload(fileName, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='name,id').execute()
    fileID = file.get('id')
    print('File ID: %s ' % fileID)
    print('File Name: %s \n' % file.get('name'))
    
    return fileID

def createNewFolder(service,  name):
    """Will create a new folder in the root of the supplied GDrive,
    doesn't check if a folder with same name already exists.
    Retruns:
        The id of the newly created folder
    """
    folder_metadata = {
        'name' : name,
        'mimeType' : 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=folder_metadata, fields='id, name').execute()
    print('Folder Creation Complete')
    folderID = folder.get('id')
    print('Folder Name: %s' % folder.get('name'))
    print('Folder ID: %s \n' % folderID)
    return folderID

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
    service = discovery.build(serviceName="drive", version="v3", credentials=credentials)
    
    print("Service acquired!")
    return service




# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

