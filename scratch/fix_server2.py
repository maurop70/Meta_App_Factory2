import os

with open('Alpha_V2_Genesis/server.py', 'a', encoding='utf-8') as f:
    f.write('''

if __name__ == "__main__":
    import threading
    # Wait briefly then warm up
    threading.Timer(2.0, warm_up_system).start()
    
    # Run server
    app.run(host="0.0.0.0", port=5008, debug=False)
''')

print("Restored main block in server.py")
