import traceback
from fastapi.testclient import TestClient
from api import app

try:
    client = TestClient(app)
    response = client.post('/api/chat/stream', json={'prompt': 'hello', 'project_name': 'test'})
    print(response.status_code)
    print(response.text)
except Exception as e:
    traceback.print_exc()
