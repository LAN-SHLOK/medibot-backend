import sqlite3

def init_db():
    conn = sqlite3.connect('medibot.db')
    cursor = conn.cursor()
    
    # "auth_method" tells us if they used Firebase or Password
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,   -- Firebase UID or "local_xyz"
            email TEXT UNIQUE NOT NULL,
            username TEXT,
            password_hash TEXT,             -- NULL if using Firebase
            auth_method TEXT DEFAULT 'manual', 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    print("✅ Database ready for Hybrid Auth.")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()