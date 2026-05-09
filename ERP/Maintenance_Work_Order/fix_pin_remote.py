import subprocess

db_path = "/opt/erp/backend/data/maintenance_erp.db"
hash_val = "$2b$12$R7rwq4x7Cwm/WDDjsMFgPeGexTFN095ftMTYuEpSgAgW5zGWIoYpC"

command1 = [
    "ssh", "-i", "C:\\Users\\mpetr\\.ssh\\id_rsa", "root@68.183.30.128",
    f"sqlite3 {db_path} \"UPDATE erp_employees SET pin_hash='{hash_val}' WHERE id='ERP-1000';\""
]

command2 = [
    "ssh", "-i", "C:\\Users\\mpetr\\.ssh\\id_rsa", "root@68.183.30.128",
    f"sqlite3 {db_path} \"UPDATE erp_employees SET role='ADMINISTRATOR' WHERE id='ERP-1000';\""
]

command3 = [
    "ssh", "-i", "C:\\Users\\mpetr\\.ssh\\id_rsa", "root@68.183.30.128",
    f"sqlite3 {db_path} \"SELECT id, role, pin_hash FROM erp_employees WHERE id='ERP-1000';\""
]

subprocess.run(command1)
subprocess.run(command2)
subprocess.run(command3)
