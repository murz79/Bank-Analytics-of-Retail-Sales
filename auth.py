import bcrypt
import pandas as pd
from database import get_connection

def authenticate(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, hashed_password, full_name, role, supervisor_id FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    if user and bcrypt.checkpw(password.encode(), user[1].encode()):
        return user
    return None

def register_user(username, password, full_name, role, supervisor_id=None):
    conn = get_connection()
    c = conn.cursor()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        c.execute("INSERT INTO users (username, hashed_password, full_name, role, supervisor_id) VALUES (?,?,?,?,?)",
                  (username, hashed, full_name, role, supervisor_id))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def delete_user(user_id):
    if user_id == 1:
        return False
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return True

def get_all_users():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, username, full_name, role, supervisor_id FROM users", conn)
    conn.close()
    return df

def get_supervisors():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, full_name FROM users WHERE role='supervisor'", conn)
    conn.close()
    return df