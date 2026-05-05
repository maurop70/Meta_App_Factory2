import sys
sys.path.insert(0, '.')
from maintenance_backend import get_db_connection
conn = get_db_connection()
c = conn.cursor()
c.execute("PRAGMA table_info(erp_employees)")
print('erp_employees:', [r['name'] for r in c.fetchall()])
c.execute("PRAGMA table_info(users)")
print('users:', [r['name'] for r in c.fetchall()])

c.execute("SELECT user_id, pin_code, role FROM users WHERE role='ADMINISTRATOR' OR role='ADMIN'")
print('Admins (users):', [dict(r) for r in c.fetchall()])

c.execute("SELECT user_id, pin_code, role FROM erp_employees WHERE role='ADMINISTRATOR' OR role='ADMIN'")
print('Admins (erp_employees):', [dict(r) for r in c.fetchall()])

