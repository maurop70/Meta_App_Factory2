import sqlite3

def dump_schema():
    conn = sqlite3.connect('data/maintenance_erp.db')
    c = conn.cursor()
    c.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    
    with open('remote_init.py', 'w') as f:
        f.write("import sqlite3\n")
        f.write("import os\n")
        f.write("os.makedirs('data', exist_ok=True)\n")
        f.write("conn = sqlite3.connect('data/maintenance_erp.db')\n")
        f.write("c = conn.cursor()\n\n")
        
        for table in tables:
            if table[0] and not table[0].startswith('CREATE TABLE sqlite_'):
                sql = table[0].replace('\n', ' ')
                f.write(f"c.execute('''{sql}''')\n")
        
        # Seed the IAM Gateway administrator profile (ERP-1000 or ERP-3000)
        # Assuming the hash for "1234" or whatever. 
        # In a previous script it was '1234' or 'abc'.
        # Let's seed ERP-1000 and ERP-3000
        f.write("c.execute(\"INSERT OR IGNORE INTO erp_employees (id, name, role, pin_hash, is_active) VALUES ('ERP-1000', 'Hub Manager', 'HM', '1234', 1)\")\n")
        f.write("c.execute(\"INSERT OR IGNORE INTO erp_employees (id, name, role, pin_hash, is_active) VALUES ('ERP-3000', 'Test Tech', 'TECH', '1234', 1)\")\n")
        
        f.write("conn.commit()\n")
        f.write("conn.close()\n")
        f.write("print('Schema and Identity Seed successfully instantiated.')\n")

if __name__ == '__main__':
    dump_schema()
