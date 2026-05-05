import sqlite3
print(sqlite3.connect('data/maintenance_erp.db').cursor().execute("SELECT role FROM erp_employees WHERE id='ERP-1000'").fetchone())
