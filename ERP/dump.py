import sqlite3

with sqlite3.connect('maintenance_erp.db') as con:
    with open('seed_state.sql', 'w') as f:
        for line in con.iterdump():
            f.write('%s\n' % line)
