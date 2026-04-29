import sqlite3

def get_admins():
    conn = sqlite3.connect('erp_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, authorization_level FROM erp_employees WHERE authorization_level IN ('ADMIN', 'ADMINISTRATOR')")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Name: {row[1]}, Role: {row[2]}")
    conn.close()

if __name__ == '__main__':
    get_admins()
