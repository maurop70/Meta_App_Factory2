import requests
try:
    r = requests.get('http://127.0.0.1:8000/api/orders/active')
    print("STATUS:", r.status_code)
    try:
        print("JSON:", r.json())
    except:
        print("TEXT:", r.text)
except Exception as e:
    print("ERROR:", e)
