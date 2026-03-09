import sqlite3
import hashlib
import pandas as pd
import numpy as np
import os
import json
import io
import zipfile
from datetime import datetime
from components.gs_sync import sync_user_created, sync_user_balance, sync_transaction
from components.drive_client import upload_file_to_drive, download_file_from_drive, get_latest_db_file_name
import streamlit as st

# libSQL para Turso
try:
    import libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

# Register adapters for numpy types
sqlite3.register_adapter(np.int64, int)
sqlite3.register_adapter(np.int32, int)

DB_NAME = "petro_arena.db"

def get_connection():
    turso_url = st.secrets.get("TURSO_URL")
    turso_token = st.secrets.get("TURSO_TOKEN")
    
    if HAS_LIBSQL and turso_url and turso_token:
        return libsql.connect(turso_url, auth_token=turso_token)
    return sqlite3.connect(DB_NAME)

# --- CONFIGURAÇÃO GOOGLE DRIVE ---
# Substitua o valor abaixo pelo ID da sua pasta do Google Drive conforme o Passo 6 do manual
GOOGLE_DRIVE_BACKUP_FOLDER_ID = "1VJjyPz_miyG48JuhgAIkb89lRdvQAsiBeiw-nhGLLlI"

@st.cache_resource
def init_db():
    # Se estamos usando Turso, não precisamos do backup do Drive para carregar o banco
    turso_url = st.secrets.get("TURSO_URL")
    if turso_url:
        conn = get_connection()
    else:
        # Check for DB in Google Drive and download if available
        try:
            drive_folder_id = st.secrets.get("google_drive_folder_id") or GOOGLE_DRIVE_BACKUP_FOLDER_ID
            if drive_folder_id and drive_folder_id != "SEU_ID_DA_PASTA_DO_GOOGLE_DRIVE_AQUI":
                latest_db_file_name = get_latest_db_file_name(drive_folder_id)
                if latest_db_file_name and not os.path.exists(DB_NAME):
                    # Usar toast para mensagens não intrusivas na inicialização
                    st.toast(f"Baixando banco de dados: {latest_db_file_name}", icon="ℹ️")
                    download_file_from_drive(latest_db_file_name, DB_NAME, drive_folder_id)
                elif not os.path.exists(DB_NAME):
                    print("Banco de dados local não encontrado. Criando um novo.")
        except Exception as e:
            # Registrar erro silenciosamente no console ou toast discreto
            print(f"Erro de sincronização: {e}")
            # st.toast(f"Sincronização offline: {e}", icon="⚠️")

        conn = get_connection()
    c = conn.cursor()
    
    # Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Jogador',
            balance INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            avatar_url TEXT,
            streak_days INTEGER DEFAULT 0,
            last_login_date TEXT
        )
    ''')
    
    # Store Items Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS store_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            cost INTEGER NOT NULL,
            image_url TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Transactions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # Purchase Requests Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS purchase_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            status TEXT DEFAULT 'PENDING',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(item_id) REFERENCES store_items(id)
        )
    ''')
    
    # Audit Logs Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT NOT NULL,
            target_id INTEGER,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(admin_id) REFERENCES users(id)
        )
    ''')
    
    # Level Configuration Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS level_config (
            level_name TEXT PRIMARY KEY,
            min_points INTEGER NOT NULL,
            badge_icon TEXT
        )
    ''')
    
    c.execute("SELECT count(*) FROM level_config")
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR IGNORE INTO level_config VALUES ('Bronze', 0, '🥉')")
        c.execute("INSERT OR IGNORE INTO level_config VALUES ('Prata', 1000, '🥈')")
        c.execute("INSERT OR IGNORE INTO level_config VALUES ('Ouro', 5000, '🥇')")
        c.execute("INSERT OR IGNORE INTO level_config VALUES ('Diamante', 10000, '💎')")
    
    # Notifications Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Missions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            reward INTEGER NOT NULL,
            deadline DATETIME,
            requirements TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')

    # Player Missions Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS player_missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mission_id INTEGER,
            status TEXT DEFAULT 'accepted',
            progress INTEGER DEFAULT 0,
            accepted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            proof_url TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        )
    ''')

    # Report Schedules Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS report_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            frequency TEXT NOT NULL,
            email TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Default admin
    try:
        c.execute("INSERT OR IGNORE INTO users (username, email, password, role, balance) VALUES (?, ?, ?, ?, ?)",
                  ("admin", "admin@petro.com", hash_password("admin123"), "Administrador", 0))
    except Exception:
        pass
        
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate_user(email, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, role, balance, avatar_url, streak_days FROM users WHERE email = ? AND password = ?", 
              (email, hash_password(password)))
    user = c.fetchone()
    conn.close()
    return user

def create_user(username, email, password, role='Jogador'):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, email, password, role, balance, streak_days, last_login_date) VALUES (?, ?, ?, ?, ?, 0, NULL)",
                  (username, email, hash_password(password), role, 0))
        conn.commit()
        new_id = c.lastrowid
        c.execute("SELECT id, username, email, role, balance, created_at FROM users WHERE id = ?", (new_id,))
        row = c.fetchone()
        if row:
            sync_user_created({
                "id": row[0], "username": row[1], "email": row[2], "role": row[3], "balance": row[4], "created_at": row[5],
            })
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_all_users():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, username, email, role, balance, created_at, streak_days, avatar_url, last_login_date FROM users", conn)
    
    # Adicionar informação de nível
    levels = pd.read_sql_query("SELECT level_name, min_points FROM level_config ORDER BY min_points ASC", conn)
    conn.close()
    
    def get_level_name(points):
        level = "Iniciante"
        for _, l in levels.iterrows():
            if points >= l['min_points']:
                level = l['level_name']
        return level
    
    if not df.empty:
        df['level'] = df['balance'].apply(get_level_name)
    else:
        df['level'] = None
        
    return df

def get_leaderboard(sort_by='balance'):
    conn = get_connection()
    # Map 'date' to 'created_at' for SQLite
    actual_sort = 'created_at' if sort_by == 'date' else 'balance'
    query = f"SELECT username, balance, role, created_at FROM users ORDER BY {actual_sort} DESC"
    df = pd.read_sql_query(query, conn)
    
    # Adicionar informação de nível
    levels = pd.read_sql_query("SELECT level_name, min_points FROM level_config ORDER BY min_points ASC", conn)
    conn.close()
    
    def get_level_name(points):
        level = "Iniciante"
        for _, l in levels.iterrows():
            if points >= l['min_points']:
                level = l['level_name']
        return level
    
    if not df.empty:
        df['level'] = df['balance'].apply(get_level_name)
    else:
        df['level'] = None
        
    return df

def log_audit_action(admin_id, action, target_id=None, details=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO audit_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
              (admin_id, action, target_id, details))
    conn.commit()
    conn.close()

def sync_db_to_drive():
    # Se estamos usando Turso, o banco já está na nuvem
    if st.secrets.get("TURSO_URL"):
        return
    
    drive_folder_id = st.secrets.get("google_drive_folder_id") or GOOGLE_DRIVE_BACKUP_FOLDER_ID
    if not drive_folder_id or drive_folder_id == "SEU_ID_DA_PASTA_DO_GOOGLE_DRIVE_AQUI":
        st.error("ID da pasta do Google Drive não configurado.")
        return
    if os.path.exists(DB_NAME):
        try:
            filename = f"petro_arena_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            upload_file_to_drive(DB_NAME, drive_folder_id, file_name=filename)
            st.success("Sincronizado!")
        except Exception as e:
            st.error(f"Erro: {e}")

def get_db_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in c.fetchall() if row[0] != 'sqlite_sequence']
    conn.close()
    return tables

def export_to_sql():
    conn = get_connection()
    sql = "\n".join(conn.iterdump())
    conn.close()
    return sql

def export_to_csv_zip():
    tables = get_db_tables()
    conn = get_connection()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for table in tables:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            zf.writestr(f"{table}.csv", df.to_csv(index=False))
    conn.close()
    zip_buffer.seek(0)
    return zip_buffer

def export_to_json_zip():
    tables = get_db_tables()
    conn = get_connection()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for table in tables:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            zf.writestr(f"{table}.json", df.to_json(orient='records', indent=2))
    conn.close()
    zip_buffer.seek(0)
    return zip_buffer

def get_db_file_bytes():
    if os.path.exists(DB_NAME):
        with open(DB_NAME, 'rb') as f: return f.read()
    return None

def restore_from_db_file(file_bytes):
    if file_bytes[:16] != b'SQLite format 3\x00': return False, "Inválido"
    with open(DB_NAME, 'wb') as f: f.write(file_bytes)
    return True, "Restaurado!"

def restore_from_sql(sql_script):
    try:
        conn = get_connection()
        conn.executescript(sql_script)
        conn.commit()
        conn.close()
        return True, "Sucesso!"
    except Exception as e: return False, str(e)

def get_user_by_email(email):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, role, balance, avatar_url, streak_days FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    return user

def update_avatar(user_id, avatar_url):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user_id))
    conn.commit()
    conn.close()

def remove_avatar(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT avatar_url FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    if res and res[0]:
        try: os.remove(res[0])
        except: pass
    c.execute("UPDATE users SET avatar_url = NULL WHERE id = ?", (user_id,))
    c.execute("INSERT INTO audit_logs (admin_id, action, target_id, details) VALUES (?, 'REMOVE_AVATAR', ?, 'Remoção de avatar')", (None, user_id))
    conn.commit()
    conn.close()
    return True, "Removido"

def get_users_paginated(page=1, per_page=10, search_query=""):
    conn = get_connection()
    offset = (page - 1) * per_page
    base = "SELECT id, username, email, role, balance, created_at, last_login_date FROM users"
    count_q = "SELECT COUNT(*) FROM users"
    params = []
    if search_query:
        f = " WHERE username LIKE ? OR email LIKE ? OR id LIKE ?"
        base += f
        count_q += f
        params = [f"%{search_query}%"] * 3
    base += " ORDER BY id DESC LIMIT ? OFFSET ?"
    c = conn.cursor()
    c.execute(count_q, params)
    total = c.fetchone()[0]
    df = pd.read_sql_query(base, conn, params=params + [per_page, offset])
    
    # Adicionar informação de nível
    levels = pd.read_sql_query("SELECT level_name, min_points FROM level_config ORDER BY min_points ASC", conn)
    conn.close()
    
    def get_level_name(points):
        level = "Iniciante"
        for _, l in levels.iterrows():
            if points >= l['min_points']:
                level = l['level_name']
        return level
    
    if not df.empty:
        df['level'] = df['balance'].apply(get_level_name)
    else:
        df['level'] = None
        
    return df, total

def get_user_full_details(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, email, role, balance, created_at, last_login_date, avatar_url, streak_days FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    
    if row:
        res = dict(zip(["id", "username", "email", "role", "balance", "created_at", "last_login_date", "avatar_url", "streak_days"], row))
        
        # Adicionar informação de nível
        c.execute("SELECT level_name, min_points FROM level_config ORDER BY min_points ASC")
        levels = c.fetchall()
        conn.close()
        
        level_name = "Iniciante"
        for l_name, min_pts in levels:
            if res['balance'] >= min_pts:
                level_name = l_name
        res['level'] = level_name
        return res
        
    conn.close()
    return None

def verify_admin_password(admin_id, password_input):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE id = ?", (admin_id,))
    res = c.fetchone()
    conn.close()
    return res and res[0] == hash_password(password_input)

def update_points(user_id, points, description, transaction_type='EARN', admin_id=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    curr = c.fetchone()[0]
    new_bal = curr + points if transaction_type == 'EARN' else curr - points
    if transaction_type == 'PENALTY' and new_bal < 0: new_bal = 0
    c.execute("UPDATE users SET balance = ? WHERE id = ?", (new_bal, user_id))
    c.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)", (user_id, transaction_type, points, description))
    if admin_id: c.execute("INSERT INTO audit_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)", (admin_id, f"POINTS_{transaction_type}", user_id, f"{points} pts: {description}"))
    conn.commit()
    tx_id = c.lastrowid
    c.execute("SELECT username, email FROM users WHERE id = ?", (user_id,))
    u = c.fetchone()
    sync_user_balance(user_id, new_bal, username=u[0], email=u[1])
    c.execute("SELECT id, user_id, type, amount, description, timestamp FROM transactions WHERE id = ?", (tx_id,))
    trow = c.fetchone()
    if trow: sync_transaction({"id": trow[0], "user_id": trow[1], "username": u[0], "type": trow[2], "amount": trow[3], "description": trow[4], "timestamp": trow[5]})
    conn.close()

def apply_penalty(user_id, points, reason, admin_id):
    update_points(user_id, points, reason, 'PENALTY', admin_id)

def add_notification(user_id, message):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO notifications (user_id, message) VALUES (?, ?)", (user_id, message))
    conn.commit()
    conn.close()

def get_user_notifications(user_id):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM notifications WHERE user_id = ? ORDER BY timestamp DESC", conn, params=(user_id,))
    conn.close()
    return df

def get_audit_logs():
    conn = get_connection()
    df = pd.read_sql_query("SELECT a.*, u.username as admin_name FROM audit_logs a LEFT JOIN users u ON a.admin_id = u.id ORDER BY a.timestamp DESC", conn)
    conn.close()
    return df

def get_store_items():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM store_items WHERE is_active = 1", conn)
    conn.close()
    return df

def add_store_item(name, description, cost):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO store_items (name, description, cost) VALUES (?, ?, ?)", (name, description, cost))
    conn.commit()
    conn.close()

def delete_store_item(item_id, admin_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE store_items SET is_active = 0 WHERE id = ?", (item_id,))
    c.execute("INSERT INTO audit_logs (admin_id, action, target_id, details) VALUES (?, 'DELETE_ITEM', ?, 'Item desativado')", (admin_id, item_id))
    conn.commit()
    conn.close()
    return True, "Item removido"

def get_pending_requests():
    conn = get_connection()
    query = """
        SELECT pr.*, u.username, u.balance, si.name as item_name, si.cost
        FROM purchase_requests pr
        JOIN users u ON pr.user_id = u.id
        JOIN store_items si ON pr.item_id = si.id
        WHERE pr.status = 'PENDING'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def process_purchase_request(req_id, action, admin_id, reason=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, item_id FROM purchase_requests WHERE id = ?", (req_id,))
    req = c.fetchone()
    if not req: return False
    uid, item_id = req
    
    # Obter nome do item para notificações
    c.execute("SELECT name, cost FROM store_items WHERE id = ?", (item_id,))
    item_data = c.fetchone()
    item_name = item_data[0]
    item_cost = item_data[1]

    if action == 'APPROVE':
        c.execute("SELECT balance FROM users WHERE id = ?", (uid,))
        bal = c.fetchone()[0]
        if bal < item_cost: return False
        c.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (item_cost, uid))
        c.execute("UPDATE purchase_requests SET status = 'APPROVED' WHERE id = ?", (req_id,))
        c.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, 'SPEND', ?, ?)", (uid, item_cost, f"Compra: {item_name}"))
        tx_id = c.lastrowid
        conn.commit()
        
        # Sincronização Google Sheets
        c.execute("SELECT username, email, balance FROM users WHERE id = ?", (uid,))
        u = c.fetchone()
        sync_user_balance(uid, u[2], username=u[0], email=u[1])
        c.execute("SELECT id, user_id, type, amount, description, timestamp FROM transactions WHERE id = ?", (tx_id,))
        trow = c.fetchone()
        if trow: sync_transaction({"id": trow[0], "user_id": trow[1], "username": u[0], "type": trow[2], "amount": trow[3], "description": trow[4], "timestamp": trow[5]})
        
        # Notificação de Aprovação
        add_notification(uid, f"SUCESSO: Sua compra de '{item_name}' foi aprovada!")
    else:
        c.execute("UPDATE purchase_requests SET status = 'REJECTED' WHERE id = ?", (req_id,))
        conn.commit()
        
        # Notificação de Rejeição com Motivo
        msg = f"NEGADO: Sua compra de '{item_name}' foi recusada."
        if reason:
            msg += f" Motivo: {reason}"
        add_notification(uid, msg)
        
    conn.close()
    return True

def get_level_config():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM level_config", conn)
    conn.close()
    return df

def update_level_threshold(name, points):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE level_config SET min_points = ? WHERE level_name = ?", (points, name))
    conn.commit()
    conn.close()

def create_mission(title, desc, reward, deadline, req):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO missions (title, description, reward, deadline, requirements) VALUES (?, ?, ?, ?, ?)", (title, desc, reward, deadline, req))
    conn.commit()
    conn.close()

def get_all_missions():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM missions", conn)
    conn.close()
    return df

def delete_mission(mid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM missions WHERE id = ?", (mid,))
    conn.commit()
    conn.close()

def get_player_missions(uid):
    conn = get_connection()
    query = "SELECT pm.*, m.title, m.description, m.reward, m.deadline FROM player_missions pm JOIN missions m ON pm.mission_id = m.id WHERE pm.user_id = ?"
    df = pd.read_sql_query(query, conn, params=(uid,))
    conn.close()
    return df

def get_available_missions(uid):
    conn = get_connection()
    query = "SELECT * FROM missions WHERE status = 'active' AND id NOT IN (SELECT mission_id FROM player_missions WHERE user_id = ?)"
    df = pd.read_sql_query(query, conn, params=(uid,))
    conn.close()
    return df

def accept_mission(uid, mid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO player_missions (user_id, mission_id) VALUES (?, ?)", (uid, mid))
    conn.commit()
    conn.close()
    return True, "Aceita"

def get_pending_mission_validations():
    conn = get_connection()
    query = "SELECT pm.*, u.username, m.title as mission_title, m.reward FROM player_missions pm JOIN users u ON pm.user_id = u.id JOIN missions m ON pm.mission_id = m.id WHERE pm.status = 'pending_validation'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def process_mission_validation(pmid, action, justification, admin_id):
    conn = get_connection()
    c = conn.cursor()
    if action == 'APPROVE':
        c.execute("SELECT user_id, mission_id FROM player_missions WHERE id = ?", (pmid,))
        uid, mid = c.fetchone()
        c.execute("SELECT reward, title FROM missions WHERE id = ?", (mid,))
        rew, title = c.fetchone()
        c.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (rew, uid))
        c.execute("UPDATE player_missions SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (pmid,))
        c.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?, 'EARN', ?, ?)", (uid, rew, f"Missão: {title}"))
        tx_id = c.lastrowid
        conn.commit()

        # Sincronização Google Sheets
        c.execute("SELECT username, email, balance FROM users WHERE id = ?", (uid,))
        u = c.fetchone()
        sync_user_balance(uid, u[2], username=u[0], email=u[1])
        c.execute("SELECT id, user_id, type, amount, description, timestamp FROM transactions WHERE id = ?", (tx_id,))
        trow = c.fetchone()
        if trow: sync_transaction({"id": trow[0], "user_id": trow[1], "username": u[0], "type": trow[2], "amount": trow[3], "description": trow[4], "timestamp": trow[5]})
    else:
        c.execute("UPDATE player_missions SET status = 'rejected' WHERE id = ?", (pmid,))
        conn.commit()
    conn.close()
    return True, "Processado"

def get_report_data(rtype, filters):
    conn = get_connection()
    if rtype == 'users': q = "SELECT * FROM users"
    elif rtype == 'transactions': q = "SELECT * FROM transactions"
    else: q = "SELECT * FROM player_missions"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df

def create_report_schedule(rtype, freq, email):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO report_schedules (report_type, frequency, email) VALUES (?, ?, ?)", (rtype, freq, email))
    conn.commit()
    conn.close()

def get_report_schedules():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM report_schedules", conn)
    conn.close()
    return df

def delete_report_schedule(sid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM report_schedules WHERE id = ?", (sid,))
    conn.commit()
    conn.close()

def reset_password(uid, pwd, admin_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET password = ? WHERE id = ?", (hash_password(pwd), uid))
    c.execute("INSERT INTO audit_logs (admin_id, action, target_id, details) VALUES (?, 'RESET_PASSWORD', ?, 'Senha resetada')", (admin_id, uid))
    conn.commit()
    conn.close()

def check_user_dependencies(uid):
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM transactions WHERE user_id = ?", (uid,))
    tx_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM purchase_requests WHERE user_id = ?", (uid,))
    pr_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (uid,))
    notif_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM player_missions WHERE user_id = ?", (uid,))
    pm_count = c.fetchone()[0]
    
    conn.close()
    
    return {
        "transactions": tx_count,
        "purchase_requests": pr_count,
        "notifications": notif_count,
        "player_missions": pm_count
    }

def delete_user(uid, admin_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        # Excluir dependências primeiro
        c.execute("DELETE FROM transactions WHERE user_id = ?", (uid,))
        c.execute("DELETE FROM purchase_requests WHERE user_id = ?", (uid,))
        c.execute("DELETE FROM notifications WHERE user_id = ?", (uid,))
        c.execute("DELETE FROM player_missions WHERE user_id = ?", (uid,))
        
        # Excluir usuário
        c.execute("DELETE FROM users WHERE id = ?", (uid,))
        
        # Auditoria
        c.execute("INSERT INTO audit_logs (admin_id, action, target_id, details) VALUES (?, 'DELETE_USER', ?, 'Usuário e dados vinculados removidos')", (admin_id, uid))
        
        conn.commit()
        return True, "Agente e todos os seus dados vinculados foram removidos do sistema."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def request_purchase(user_id, item_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO purchase_requests (user_id, item_id) VALUES (?, ?)", (user_id, item_id))
    conn.commit()
    conn.close()
    return True, "Solicitação de compra enviada"

def request_mission_validation(pm_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE player_missions SET status = 'pending_validation' WHERE id = ?", (pm_id,))
    conn.commit()
    conn.close()
    return True, "Validação solicitada com sucesso!"

def get_user_history(user_id):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC", conn, params=(user_id,))
    conn.close()
    return df

def mark_notification_read(notif_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return True
