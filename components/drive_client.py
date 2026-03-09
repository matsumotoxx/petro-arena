from typing import Any, Dict, List, Optional, Tuple
import streamlit as st
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from google_auth_oauthlib.flow import InstalledAppFlow
import os
import json

SCOPES = ["https://www.googleapis.com/auth/drive"]

def _get_gauth() -> GoogleAuth:
    gauth = GoogleAuth()
    
    # Prioridade para o arquivo service_account.json na raiz conforme manual
    if os.path.exists("service_account.json"):
        try:
            gauth.LoadServiceAccountCredentials("service_account.json", SCOPES)
            return gauth
        except Exception as e:
            print(f"Erro ao carregar service_account.json: {e}")

    # Fallback para o caminho nos segredos do Streamlit
    path = st.secrets.get("gcp_service_account_path", None)
    if path and os.path.exists(path):
        try:
            gauth.LoadServiceAccountCredentials(path, SCOPES)
            return gauth
        except Exception:
            pass
            
    # Fallback para configuração direta nos segredos
    cfg = st.secrets.get("gcp_service_account", None)
    if cfg:
        try:
            temp_file_path = "temp_service_account.json"
            with open(temp_file_path, "w") as f:
                json.dump(dict(cfg), f)
            gauth.LoadServiceAccountCredentials(temp_file_path, SCOPES)
            os.remove(temp_file_path)
            return gauth
        except Exception:
            pass

    # Fallback para OAuth se nada acima funcionar
    token_path = st.secrets.get("gcp_oauth_token_path", "token.json")
    if os.path.exists(token_path):
        gauth.LoadCredentialsFile(token_path)

    if gauth.credentials is None:
        client_secret_path = st.secrets.get("gcp_oauth_client_secret_path", "client_secret.json")
        if os.path.exists(client_secret_path):
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            gauth.credentials = creds
            with open(token_path, "w") as token:
                token.write(gauth.credentials.to_json())
        else:
            raise RuntimeError("Nenhuma credencial do Google configurada (Service Account ou OAuth)")
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    
    return gauth

def get_drive_client() -> GoogleDrive:
    gauth = _get_gauth()
    return GoogleDrive(gauth)

def upload_file_to_drive(file_path: str, folder_id: Optional[str] = None, file_name: Optional[str] = None) -> str:
    drive = get_drive_client()
    if file_name is None:
        file_name = os.path.basename(file_path)

    # Verifica se arquivo já existe
    query = f"'{folder_id if folder_id else 'root'}' in parents and title = '{file_name}' and trashed=false"
    file_list = drive.ListFile({'q': query}).GetList()

    if file_list:
        file = file_list[0]
    else:
        file_metadata = {'title': file_name}
        if folder_id:
            file_metadata['parents'] = [{'id': folder_id}]
        file = drive.CreateFile(file_metadata)
    
    file.SetContentFile(file_path)
    file.Upload()
    return file['id']

def download_file_from_drive(file_name: str, local_path: str, folder_id: Optional[str] = None) -> bool:
    drive = get_drive_client()
    query = f"'{folder_id if folder_id else 'root'}' in parents and title = '{file_name}' and trashed=false"
    file_list = drive.ListFile({'q': query}).GetList()

    if file_list:
        file = file_list[0]
        file.GetContentFile(local_path)
        return True
    return False

def get_latest_db_file_name(folder_id: Optional[str] = None) -> Optional[str]:
    drive = get_drive_client()
    query = f"'{folder_id if folder_id else 'root'}' in parents and title contains 'petro_arena_full_' and trashed=false"
    file_list = drive.ListFile({'q': query, 'orderBy': 'modifiedDate desc'}).GetList()
    if file_list:
        return file_list[0]['title']
    return None
