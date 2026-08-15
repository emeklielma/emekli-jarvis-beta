import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "jarvis_memory.db")

def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_memory(key: str, value: str, category: str = "general") -> bool:
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if key exists
        cursor.execute('SELECT id FROM memories WHERE key = ?', (key,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('UPDATE memories SET value = ?, category = ?, created_at = CURRENT_TIMESTAMP WHERE key = ?', (value, category, key))
        else:
            cursor.execute('INSERT INTO memories (key, value, category) VALUES (?, ?, ?)', (key, value, category))
            
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[MEMORY ERROR] {e}")
        return False

def get_all_memories():
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT key, value, category FROM memories ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [{"key": r[0], "value": r[1], "category": r[2]} for r in rows]
    except Exception as e:
        print(f"[MEMORY ERROR] {e}")
        return []

def search_memory(query: str):
    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        search_query = f"%{query}%"
        cursor.execute('SELECT key, value, category FROM memories WHERE key LIKE ? OR value LIKE ? OR category LIKE ?', (search_query, search_query, search_query))
        rows = cursor.fetchall()
        conn.close()
        return [{"key": r[0], "value": r[1], "category": r[2]} for r in rows]
    except Exception as e:
        print(f"[MEMORY ERROR] {e}")
        return []

# Initialize DB on load
init_db()
