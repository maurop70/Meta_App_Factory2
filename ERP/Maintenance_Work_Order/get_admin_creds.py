import sys
sys.path.insert(0, '.')
from maintenance_backend import get_db_connection
conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print('Tables:', tables)
if ('erp_employees',) in tables:
    c.execute("SELECT id, pin, role FROM erp_employees WHERE role='ADMINISTRATOR' OR role='ADMIN'")
    print('Admins (erp_employees):', c.fetchall())
if ('users',) in tables:
    c.execute("SELECT id, pin, role FROM users WHERE role='ADMINISTRATOR' OR role='ADMIN'")
    print('Admins (users):', c.fetchall())
