from typing import Any, Dict, List, Optional, Tuple
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def _client_service_account() -> Optional[gspread.client.Client]:
    path = st.secrets.get("gcp_service_account_path", None)
    if path:
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                info = json.load(f)
            pk = info.get("private_key")
            if isinstance(pk, str):
                info["private_key"] = pk.replace("\\n", "\n")
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception:
            pass
    cfg = st.secrets.get("gcp_service_account", None)
    if cfg:
        try:
            pk = cfg.get("private_key")
            if isinstance(pk, str):
                cfg["private_key"] = pk.replace("\\n", "\n")
            creds = Credentials.from_service_account_info(cfg, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception:
            pass
    return None

def _client_oauth() -> Optional[gspread.client.Client]:
    client_secret_path = st.secrets.get("gcp_oauth_client_secret_path", "client_secret.json")
    token_path = st.secrets.get("gcp_oauth_token_path", "token.json")
    creds = None
    if os.path.exists(token_path):
        try:
            from google.oauth2.credentials import Credentials as UserCreds
            creds = UserCreds.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return gspread.authorize(creds)

def get_client() -> gspread.client.Client:
    cli = _client_service_account()
    if cli:
        return cli
    cli = _client_oauth()
    if cli:
        return cli
    raise RuntimeError("Credenciais do Google não configuradas")

@st.cache_data(ttl=60)
def read_rows(
    spreadsheet_id: str,
    worksheet_title: str,
    header: bool = True,
    expected_headers: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    cli = get_client()
    sh = cli.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_title)
    if header:
        try:
            if expected_headers:
                return ws.get_all_records(expected_headers=expected_headers)
            return ws.get_all_records()
        except Exception:
            pass
    values = ws.get_all_values()
    if not values:
        return []
    headers = expected_headers if expected_headers else values[0]
    dedup: List[str] = []
    seen: Dict[str, int] = {}
    for h in headers:
        key = str(h).strip() if h is not None else ""
        cnt = seen.get(key, 0)
        if cnt == 0:
            dedup.append(key or f"col_{len(seen)+1}")
            seen[key] = 1
        else:
            new_key = f"{key}_{cnt+1}" if key else f"col_{len(seen)+1}"
            dedup.append(new_key)
            seen[key] = cnt + 1
    data_rows = values[1:] if len(values) > 1 else []
    result: List[Dict[str, Any]] = []
    for r in data_rows:
        row_dict: Dict[str, Any] = {}
        for i, v in enumerate(r):
            k = dedup[i] if i < len(dedup) else f"col_{i+1}"
            row_dict[k] = v
        result.append(row_dict)
    return result

def append_rows(spreadsheet_id: str, worksheet_title: str, rows: List[List[Any]]) -> None:
    cli = get_client()
    sh = cli.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_title)
    ws.append_rows(rows, value_input_option="USER_ENTERED")

def update_row_by_key(spreadsheet_id: str, worksheet_title: str, key_column: str, key_value: Any, patch: Dict[str, Any]) -> bool:
    cli = get_client()
    sh = cli.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_title)
    records = ws.get_all_records()
    if not records:
        return False
    if key_column not in records[0].keys():
        return False
    idx = None
    for i, r in enumerate(records, start=2):
        if str(r.get(key_column, "")) == str(key_value):
            idx = i
            break
    if idx is None:
        return False
    headers = list(records[0].keys())
    for k, v in patch.items():
        if k in headers:
            col = headers.index(k) + 1
            ws.update_cell(idx, col, v)
    return True

def delete_row_by_key(spreadsheet_id: str, worksheet_title: str, key_column: str, key_value: Any) -> bool:
    cli = get_client()
    sh = cli.open_by_key(spreadsheet_id)
    ws = sh.worksheet(worksheet_title)
    records = ws.get_all_records()
    if not records:
        return False
    idx = None
    for i, r in enumerate(records, start=2):
        if str(r.get(key_column, "")) == str(key_value):
            idx = i
            break
    if idx is None:
        return False
    ws.delete_rows(idx)
    return True
