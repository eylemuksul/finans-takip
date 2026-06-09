import sqlite3

def init_db():
    conn = sqlite3.connect('finance.db')
    cursor = conn.cursor()

    # Users Tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Categories Tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('Gelir', 'Gider'))
        )
    ''')

    # Transactions Tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES Users (id),
            FOREIGN KEY (category_id) REFERENCES Categories (id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Veritabanı ve tablolar başarıyla oluşturuldu.")
