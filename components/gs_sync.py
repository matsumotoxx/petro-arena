import streamlit as st
import pandas as pd
from datetime import datetime
from components.google_sheets_client import append_rows, update_row_by_key

def sync_user_created(user_data: dict):
    if not st.secrets.get("gs_sync_enabled", False):
        return
    
    sheet_id = st.secrets.get("gs_users_sheet_id")
    worksheet = st.secrets.get("gs_users_ws", "users")
    
    if not sheet_id:
        return
        
    try:
        # data: id, username, email, role, balance, created_at
        row = [
            user_data.get("id"),
            user_data.get("username"),
            user_data.get("email"),
            user_data.get("role", "Jogador"),
            user_data.get("balance", 0),
            user_data.get("created_at")
        ]
        append_rows(sheet_id, worksheet, [row])
    except Exception as e:
        st.warning(f"Erro ao sincronizar novo usuário no Google Sheets: {e}")

def sync_user_balance(user_id: int, balance: int, username: str = None, email: str = None):
    if not st.secrets.get("gs_sync_enabled", False):
        return
    
    sheet_id = st.secrets.get("gs_users_sheet_id")
    worksheet = st.secrets.get("gs_users_ws", "users")
    
    if not sheet_id:
        return
        
    try:
        patch = {"balance": balance}
        # Tenta atualizar pelo ID do usuário
        success = update_row_by_key(sheet_id, worksheet, "id", user_id, patch)
        
        # Se falhar pelo ID, tenta pelo email se fornecido
        if not success and email:
            update_row_by_key(sheet_id, worksheet, "email", email, patch)
            
    except Exception as e:
        st.warning(f"Erro ao sincronizar saldo no Google Sheets: {e}")

def sync_transaction(tx_data: dict):
    if not st.secrets.get("gs_sync_enabled", False):
        return
    
    sheet_id = st.secrets.get("gs_transactions_sheet_id")
    worksheet = st.secrets.get("gs_transactions_ws", "transactions")
    
    if not sheet_id:
        # Fallback para a mesma planilha de usuários se não houver uma específica
        sheet_id = st.secrets.get("gs_users_sheet_id")
        
    if not sheet_id:
        return
        
    try:
        # data: id, user_id, username, type, amount, description, timestamp
        row = [
            tx_data.get("id"),
            tx_data.get("user_id"),
            tx_data.get("username", ""),
            tx_data.get("type"),
            tx_data.get("amount"),
            tx_data.get("description"),
            tx_data.get("timestamp")
        ]
        append_rows(sheet_id, worksheet, [row])
    except Exception as e:
        st.warning(f"Erro ao sincronizar transação no Google Sheets: {e}")
