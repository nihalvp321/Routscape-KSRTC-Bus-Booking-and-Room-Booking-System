import sqlite3

# Connect to or create the database
conn = sqlite3.connect('routescape.db')

# Create the table
conn.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT NOT NULL,
    profile_pic TEXT,
    address TEXT,
    state TEXT,
    pin TEXT,
    phone TEXT,
    gender TEXT
)
''')

conn.commit()
conn.close()
print("✅ routescape.db and users table created successfully!")
