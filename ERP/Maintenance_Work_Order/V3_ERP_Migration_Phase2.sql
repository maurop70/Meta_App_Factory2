-- ==============================================================================
-- META APP FACTORY - V3 GLOBAL ERP SCHEMA - PHASE 2 MIGRATION
-- ==============================================================================
-- This script corrects the architectural regressions by establishing formal
-- Cost Centers (Departments) and restoring the Universal Routing Matrix natively.
-- It also promotes critical JSONB fields to indexed columns for performance.

-- 1. Create erp_departments (Preserves the Universal Routing Matrix)
CREATE TABLE IF NOT EXISTS erp_departments (
    department_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_name TEXT UNIQUE NOT NULL,
    manager_id UUID REFERENCES erp_employees(user_id) ON DELETE SET NULL,
    servicing_department_id UUID REFERENCES erp_departments(department_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Create erp_sub_departments (Preserves Routing Overrides)
CREATE TABLE IF NOT EXISTS erp_sub_departments (
    sub_dept_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sub_dept_name TEXT NOT NULL,
    department_id UUID REFERENCES erp_departments(department_id) ON DELETE CASCADE,
    servicing_department_id UUID REFERENCES erp_departments(department_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Modify erp_assets to link to explicit departments instead of raw text locations
ALTER TABLE erp_assets ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES erp_departments(department_id) ON DELETE SET NULL;
ALTER TABLE erp_assets ADD COLUMN IF NOT EXISTS sub_dept_id UUID REFERENCES erp_sub_departments(sub_dept_id) ON DELETE SET NULL;

-- 4. Eliminate JSONB Table Scans: Promote Critical Auth & Routing Fields
-- Add columns
ALTER TABLE erp_employees ADD COLUMN IF NOT EXISTS phone_number TEXT UNIQUE;
ALTER TABLE erp_employees ADD COLUMN IF NOT EXISTS pin_code TEXT;
ALTER TABLE erp_employees ADD COLUMN IF NOT EXISTS department_id UUID REFERENCES erp_departments(department_id) ON DELETE SET NULL;

ALTER TABLE erp_maintenance_logs ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES erp_employees(user_id) ON DELETE SET NULL;

-- Create Indexes for fast querying
CREATE INDEX IF NOT EXISTS idx_erp_employees_phone ON erp_employees(phone_number);
CREATE INDEX IF NOT EXISTS idx_erp_employees_dept ON erp_employees(department_id);
CREATE INDEX IF NOT EXISTS idx_erp_maintenance_assigned ON erp_maintenance_logs(assigned_to);

-- 5. Data Backfill (Extract existing data from JSONB metadata if present)
UPDATE erp_employees 
SET phone_number = metadata->>'phone_number',
    pin_code = metadata->>'pin_code'
WHERE metadata->>'phone_number' IS NOT NULL;

UPDATE erp_maintenance_logs 
SET assigned_to = (metadata->>'assigned_to')::UUID
WHERE metadata->>'assigned_to' IS NOT NULL;

-- Ensure security (RLS)
ALTER TABLE erp_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_sub_departments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read departments" ON erp_departments FOR SELECT USING (true);
CREATE POLICY "Allow public insert departments" ON erp_departments FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update departments" ON erp_departments FOR UPDATE USING (true);

CREATE POLICY "Allow public read sub_departments" ON erp_sub_departments FOR SELECT USING (true);
CREATE POLICY "Allow public insert sub_departments" ON erp_sub_departments FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public update sub_departments" ON erp_sub_departments FOR UPDATE USING (true);
