import os
import sys
import httplib2
import json
from datetime import datetime
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
from io import BytesIO
from google.auth.transport.requests import Request

import os
import shutil
import glob

# Define your paths
# Replace with your own values
SRC_PATH = "/home/vaddemgen/Documents/Projects"
SAVE_FOLDER_PATH = "/home/vaddemgen/Documents/Projects/Backups"
CREDENTIALS_FILE = "/home/vaddemgen/.gcp/client_secret_1030461053350-t9lk0hleqmade9kborua753uamoddsi7.apps.googleusercontent.com.json"

# Create SAVE_FOLDER_PATH if it doesn't exist
if not os.path.exists(SAVE_FOLDER_PATH):
    os.makedirs(SAVE_FOLDER_PATH)

# Move all *.log.gz files from SRC_PATH to SAVE_FOLDER_PATH and store their names
log_files = glob.glob(os.path.join(SRC_PATH, "*.log.gz"))
moved_files = []
for file_path in log_files:
    file_name = os.path.basename(file_path)
    shutil.move(file_path, os.path.join(SAVE_FOLDER_PATH, file_name))
    moved_files.append(os.path.join(SAVE_FOLDER_PATH, file_name))

# Compress iot.db with maximum compression using gzip and keep the original
input_file = os.path.join(SRC_PATH, "iot.db")
output_file = os.path.join(SAVE_FOLDER_PATH, "iot.db.gz")
compressed_db = output_file

# Using -9 for maximum compression and -k to keep the original file
os.system(f"gzip -9 -k {input_file} -c > {output_file}")

# Replace 'YOUR_FOLDER_ID' with the actual ID of the folder you want to use on Google Drive
YOUR_FOLDER_ID = '1Hn_6d6-mW3RkREK2qGpqQH_vFJi59umx'

# Google Drive API settings
SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

# Authenticate using the Google Drive API
creds = None
# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

# Create the Google Drive API client
service = build("drive", "v3", credentials=creds)

# Helper function to get the file timestamp
def get_file_timestamp(file_path):
    stat = os.stat(file_path)
    return datetime.utcfromtimestamp(stat.st_mtime)

# Helper function to download a file from Google Drive
def download_drive_file(file_id, local_path):
    request = service.files().get_media(fileId=file_id)
    file_data = BytesIO()
    downloader = MediaIoBaseDownload(file_data, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print("Download %d%%." % int(status.progress() * 100))

    with open(local_path, "wb") as local_file:
        local_file.write(file_data.getvalue())

# Helper function to upload a file to Google Drive
def upload_drive_file(local_path, drive_folder_id):
    file_metadata = {
        "name": os.path.basename(local_path),
        "parents": [drive_folder_id]
    }
    media = MediaFileUpload(local_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    print(f"File ID: {file.get('id')}")
    return file.get("id")

# Sync local game save files with Google Drive
for root, dirs, files in os.walk(SAVE_FOLDER_PATH):
    for file in files:
        #print (file)
        local_file_path = os.path.join(root, file)
        relative_path = os.path.relpath(local_file_path, SAVE_FOLDER_PATH)

        # Get the file on Google Drive
        query = f"mimeType!='{FOLDER_MIME_TYPE}' and trashed = false and name='{relative_path}' and '{YOUR_FOLDER_ID}' in parents"
        response = service.files().list(q=query, spaces="drive", fields="nextPageToken, files(id, name, mimeType, modifiedTime)").execute()
        drive_files = response.get("files")

        # Check if the file exists on Google Drive
        if drive_files:
            drive_file = drive_files[0]
            drive_file_id = drive_file["id"]
            drive_file_timestamp = datetime.strptime(drive_file["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ")

            # Compare the file timestamps
            local_file_timestamp = get_file_timestamp(local_file_path)
            if local_file_timestamp > drive_file_timestamp:
                # Local file is newer, upload it to Google Drive
                print(f"Uploading {relative_path} to Google Drive")
                service.files().delete(fileId=drive_file_id).execute()
                upload_drive_file(local_file_path, YOUR_FOLDER_ID)
            elif local_file_timestamp < drive_file_timestamp:
                # Google Drive file is newer, download it to the local machine
                print(f"Downloading {relative_path} from Google Drive")
                download_drive_file(drive_file_id, local_file_path)
            else:
                print(f"{relative_path} is already in sync")
        else:
            # The file does not exist on Google Drive, upload it
            print(f"Uploading {relative_path} to Google Drive")
            upload_drive_file(local_file_path, YOUR_FOLDER_ID)
            
# Delete all compressed files
print("Deleting compressed files...")
for file_path in moved_files:
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Deleted: {file_path}")

if os.path.exists(compressed_db):
    os.remove(compressed_db)
    print(f"Deleted: {compressed_db}")

print("Cleanup complete.")