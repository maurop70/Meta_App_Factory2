import sys
sys.path.insert(0, '.')
from maintenance_backend import get_password_hash, get_db_connection
hash_1234 = get_password_hash('1234')
conn = get_db_connection()
c = conn.cursor()
c.execute("INSERT OR REPLACE INTO erp_employees (id, name, role, pin_hash, is_active, department_id, reports_to_hm_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
    ('PLAYWRIGHT', 'Playwright User', 'ADMINISTRATOR', hash_1234, 1, 'MAINTENANCE', None)
)
conn.commit()
print('Injected user PLAYWRIGHT with PIN 1234')
