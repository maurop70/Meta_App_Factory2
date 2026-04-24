-- Seed MWO-1004 with Mock Relational Topologies

-- Create dummy user if missing to satisfy FK
INSERT OR IGNORE INTO users (user_id, name, role, department)
VALUES ('HM-01', 'Head Manager', 'HM (Admin)', 'Facilities');

-- Create dummy location if missing
INSERT OR IGNORE INTO locations (location_id, location_name) 
VALUES ('LOC-A', 'Breakroom A');

-- Create dummy equipment if missing
INSERT OR IGNORE INTO equipment_registry (equipment_id, equipment_name, assigned_hm_id, location_id) 
VALUES ('EQ-501', 'Standard Sink Fixture', 'HM-01', 'LOC-A');

-- Actuate the specific MWO record
UPDATE work_orders 
SET 
    start_date = '2026-04-24T12:00:00.000Z',
    location_id = 'LOC-A',
    equipment_id = 'EQ-501',
    assigned_hm_id = 'HM-01'
WHERE mwo_id = 'MWO-1004';
