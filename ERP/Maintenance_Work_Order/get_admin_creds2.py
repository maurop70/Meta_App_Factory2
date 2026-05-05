import sys
sys.path.insert(0, '.')
from maintenance_backend import get_db_connection
conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [dict(row)['name'] for row in c.fetchall()]
print('Tables:', tables)
if 'erp_employees' in tables:
    try:
        c.execute("SELECT emp_id, pin_code, role FROM erp_employees WHERE role='ADMINISTRATOR' OR role='ADMIN'")
        print('Admins (erp_employees):', [dict(r) for r in c.fetchall()])
    except Exception as e:
        print(e)
if 'users' in tables:
    try:
        c.execute("SELECT id, pin, role FROM users WHERE role='ADMINISTRATOR' OR role='ADMIN'")
        print('Admins (users):', [dict(r) for r in c.fetchall()])
    except Exception as e:
        print(e)
