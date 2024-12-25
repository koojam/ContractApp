from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import os
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_google_drive_service():
    creds = None
    # Token file stores access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

def list_contracts_in_folder(folder_id):
    """List all contracts in a specific Google Drive folder"""
    service = get_google_drive_service()
    
    query = f"'{folder_id}' in parents and (mimeType='application/pdf' or mimeType='text/plain')"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, mimeType)'
    ).execute()
    
    return results.get('files', [])

def download_contract(file_id, local_path):
    """Download a contract from Google Drive"""
    service = get_google_drive_service()
    
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    
    while done is False:
        status, done = downloader.next_chunk()
        
    fh.seek(0)
    with open(local_path, 'wb') as f:
        f.write(fh.read()) 