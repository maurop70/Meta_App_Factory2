import subprocess

command = [
    "ssh", "-i", "C:\\Users\\mpetr\\.ssh\\id_rsa", "root@68.183.30.128",
    "sqlite3 /opt/erp/Maintenance_Work_Order/data/maintenance_erp.db \"UPDATE erp_employees SET role = 'ADMINISTRATOR' WHERE id = 'ERP-1000';\" && sqlite3 /opt/erp/Maintenance_Work_Order/data/maintenance_erp.db \"SELECT id, role FROM erp_employees WHERE id = 'ERP-1000';\""
]

subprocess.run(command)
