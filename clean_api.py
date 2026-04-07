import os

files = [
    'factory_ui/src/App.jsx',
    'factory_ui/src/CommandCenter.jsx',
    'factory_ui/src/WarRoom.jsx',
    'factory_ui/src/IP_SOP_Modal.jsx',
    'factory_ui/src/SupportFAB.jsx'
]

for f in files:
    if not os.path.exists(f):
        print(f"Skipping {f}, file does not exist")
        continue

    try:
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
    except UnicodeDecodeError:
        with open(f, 'r', encoding='mbcs') as file:
            content = file.read()
            
    content = content.replace("const API_BASE = 'http://localhost:5000';", "")
    content = content.replace("const WS_URL = 'ws://localhost:5000/ws/warroom';", "const WS_URL = `ws://${window.location.host}/ws/warroom`;")
    content = content.replace("${API_BASE}", "")
    content = content.replace("${API}", "")
    
    with open(f, 'w', encoding='utf-8', newline='\n') as file:
        file.write(content)
    print('Cleaned', f)
