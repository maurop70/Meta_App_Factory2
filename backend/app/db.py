import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../db/inventory.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            stock INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    
    # Check if empty, seed some data
    cursor.execute("SELECT COUNT(*) FROM inventory")
    if cursor.fetchone()[0] == 0:
        seed_data = [
            ("SKU-AG2-001", "Antigravity Thruster Coil V2", "Propulsion", 42, 12500.0, "Active"),
            ("SKU-AG2-002", "Sub-Atomic Quantum Sanitizer", "Core", 8, 45000.0, "Critical"),
            ("SKU-AG2-003", "Aegis Electromagnetic Deflector", "Defense", 112, 8900.0, "Active"),
            ("SKU-AG2-004", "Sentinel Event Queue Synchronizer", "Software", 350, 450.0, "Active"),
            ("SKU-AG2-005", "Loki Adversarial Sanitization Node", "Core", 3, 75000.0, "Critical"),
            ("SKU-AG2-006", "Venture Scout Signal Harvester", "Software", 18, 1200.0, "Active"),
            ("SKU-AG2-007", "CFO Ledgermaster Cryptographic Core", "Hardware", 14, 18500.0, "Active"),
            ("SKU-AG2-008", "Bio-Digital Neural Bridge V4", "Interface", 0, 95000.0, "Out of Stock"),
            ("SKU-AG2-009", "Hyperbaric Plasma Refinement Grid", "Hardware", 27, 3400.0, "Active"),
            ("SKU-AG2-010", "Aether Gravity Wave Transceiver", "Interface", 65, 8200.0, "Active"),
            ("SKU-AG2-011", "Chronos Temporal Buffer Module", "Propulsion", 5, 29900.0, "Critical"),
            ("SKU-AG2-012", "Holographic Brand Studio Projector", "Display", 89, 150.0, "Active"),
            ("SKU-AG2-013", "TRIAD-LOGIC", "Core", 100, 150000.0, "Active")
        ]
        cursor.executemany(
            "INSERT INTO inventory (sku, name, category, stock, price, status) VALUES (?, ?, ?, ?, ?, ?)",
            seed_data
        )
        conn.commit()
    conn.close()

def get_db_connection():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
