import sys
import subprocess

try:
    import psycopg2
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2

conn_str = "postgresql://postgres.mcznfhygdvnirxbisgzt:Gelatoshoppe1976!@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

sql = """
-- 1. Create the App Users Table (The Master Roster)
CREATE TABLE IF NOT EXISTS app_users (
    user_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    full_name TEXT NOT NULL,
    phone_number TEXT UNIQUE NOT NULL,
    department TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    app_permissions JSONB DEFAULT '{"maintenance_app": "PM"}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Create the Equipment Registry (Cascading Dropdown Source)
CREATE TABLE IF NOT EXISTS equipment_registry (
    equipment_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    equipment_name TEXT NOT NULL,
    department TEXT NOT NULL,
    production_line TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Create the Work Orders Table (The Core Ledger)
CREATE TABLE IF NOT EXISTS work_orders (
    order_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    pm_user_id UUID REFERENCES app_users(user_id),
    equipment_id UUID REFERENCES equipment_registry(equipment_id),
    pm_urgency_level TEXT NOT NULL, 
    risk_level TEXT, 
    maintenance_type TEXT, 
    problem_description TEXT NOT NULL,
    status TEXT DEFAULT 'Submitted', 
    hm_execution_index NUMERIC DEFAULT 0,
    is_archived BOOLEAN DEFAULT FALSE,
    start_date TIMESTAMP WITH TIME ZONE,
    completion_date TIMESTAMP WITH TIME ZONE,
    work_performed TEXT,
    technician_id UUID REFERENCES app_users(user_id),
    reviewed_by UUID REFERENCES app_users(user_id),
    cost NUMERIC DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Set basic read/write policies
ALTER TABLE app_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE equipment_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    CREATE POLICY "Allow all local operations" ON app_users FOR ALL USING (true);
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE POLICY "Allow all local operations" ON equipment_registry FOR ALL USING (true);
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE POLICY "Allow all local operations" ON work_orders FOR ALL USING (true);
EXCEPTION WHEN duplicate_object THEN null; END $$;
"""

try:
    conn = psycopg2.connect(conn_str)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    print("SUCCESS")
except Exception as e:
    import traceback
    print("ERROR:")
    print(traceback.format_exc())
finally:
    if 'cur' in locals() and cur:
        cur.close()
    if 'conn' in locals() and conn:
        conn.close()
