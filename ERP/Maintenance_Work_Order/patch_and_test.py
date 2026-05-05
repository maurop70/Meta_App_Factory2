import sys; sys.path.insert(0, '.')
from local_db import get_db_connection
from maintenance_backend import create_access_token
import requests

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("UPDATE work_orders SET status = 'UNASSIGNED_ESCALATION' WHERE mwo_id IN (SELECT mwo_id FROM work_orders WHERE status = 'UNASSIGNED' LIMIT 3)")
conn.commit()

cursor.execute("SELECT COUNT(*) FROM work_orders WHERE status = 'UNASSIGNED_ESCALATION'")
print('Escalation Count:', cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM work_orders WHERE status = 'UNASSIGNED'")
print('Unassigned Count:', cursor.fetchone()[0])
conn.close()

token = create_access_token(user_id='U-ADMIN', role='ADMINISTRATOR')
headers = {'Authorization': f'Bearer {token}'}
url = 'http://localhost:8000/api/work-orders/queue?status=UNASSIGNED_ESCALATION&limit=25&offset=0'
resp = requests.get(url, headers=headers)
print('Response JSON:', resp.json())
