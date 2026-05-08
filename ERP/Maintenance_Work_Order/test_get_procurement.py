import requests

auth_resp = requests.post('http://localhost:9000/api/v1/auth/login', json={'emp_id': 'ERP-1000', 'pin': '1234'})
token = auth_resp.json().get('access_token')

resp = requests.get('http://localhost:8000/admin/procurement', headers={'Authorization': f'Bearer {token}'})
print(resp.json())
