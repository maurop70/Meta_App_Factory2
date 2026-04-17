-- 1. Add Dynamic Permissions to Roles
ALTER TABLE roles ADD COLUMN IF NOT EXISTS can_submit BOOLEAN DEFAULT FALSE;
ALTER TABLE roles ADD COLUMN IF NOT EXISTS can_manage BOOLEAN DEFAULT FALSE;
ALTER TABLE roles ADD COLUMN IF NOT EXISTS can_execute BOOLEAN DEFAULT FALSE;

-- 2. Add Universal Routing Matrix to Departments & Sub-Departments
ALTER TABLE departments ADD COLUMN IF NOT EXISTS servicing_department_id UUID REFERENCES departments(department_id);
ALTER TABLE sub_departments ADD COLUMN IF NOT EXISTS servicing_department_id UUID REFERENCES departments(department_id);

-- 2.1 Link Equipment to Sub-Departments
ALTER TABLE equipment_registry ADD COLUMN IF NOT EXISTS sub_dept_ref_id UUID REFERENCES sub_departments(sub_dept_id);

-- 3. Create Native Event Dispatcher Table (app_notifications)
CREATE TABLE IF NOT EXISTS app_notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES work_orders(order_id),
    event_type TEXT NOT NULL,
    origin_dept_id UUID REFERENCES departments(department_id),
    target_dept_id UUID REFERENCES departments(department_id),
    target_user_id UUID REFERENCES app_users(user_id), -- NEW: Precision targeting
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Create Work Order History Table
CREATE TABLE IF NOT EXISTS work_order_history (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES work_orders(order_id),
    status TEXT NOT NULL,
    user_id UUID REFERENCES app_users(user_id),
    note TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Add Media Support to Work Orders
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS media_urls JSONB DEFAULT '[]';
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS target_department_id UUID REFERENCES departments(department_id);

-- 6. Role Identity Normalization
-- Add role_id column to app_users
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS role_id UUID REFERENCES roles(role_id);

-- Backfill role_id from role (text) column
UPDATE app_users
SET role_id = roles.role_id
FROM roles
WHERE app_users.role = roles.role_name;

-- (Optional) Rename 'role' to 'role_legacy' once verified
-- ALTER TABLE app_users RENAME COLUMN role TO role_legacy;
