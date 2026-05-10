import pandas as pd
from database import get_connection

def add_product(name, category, base_price):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO products (name, category, base_price) VALUES (?,?,?)", (name, category, base_price))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def delete_product(product_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()

def get_all_products():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, name, category, base_price FROM products", conn)
    conn.close()
    return df