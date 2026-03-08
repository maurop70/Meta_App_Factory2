-- ═══════════════════════════════════════════════════
--  DELEGATE AI — Supabase Schema Migration 001
--  Project Genesis | Phase 1: Schema + API
--  Filed: 2026-03-07 | Author: CTO + Data Architect
-- ═══════════════════════════════════════════════════


-- ── 1. FIRMS TABLE ──
-- Represents a law firm (tenant). All data is isolated per-firm via RLS.

CREATE TABLE IF NOT EXISTS firms (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT NOT NULL,
    size TEXT CHECK (size IN ('SOLO', 'SMALL', 'MID', 'LARGE')),
    practice_areas TEXT[] DEFAULT '{}',
    subscription_tier TEXT DEFAULT 'PILOT' CHECK (subscription_tier IN (
        'PILOT', 'STARTER', 'PROFESSIONAL', 'ENTERPRISE'
    )),
    seat_count INTEGER DEFAULT 1,
    contact_email TEXT,
    contact_name TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- ── 2. FIRM MEMBERS TABLE ──
-- Links Supabase Auth users to their firm. Enforces firm-level tenancy.

CREATE TABLE IF NOT EXISTS firm_members (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'ASSOCIATE' CHECK (role IN (
        'PARTNER', 'SENIOR_ASSOCIATE', 'ASSOCIATE', 'PARALEGAL', 'ADMIN'
    )),
    display_name TEXT NOT NULL,
    email TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, firm_id)
);

CREATE INDEX idx_firm_members_user ON firm_members(user_id);
CREATE INDEX idx_firm_members_firm ON firm_members(firm_id);


-- ── 3. DELEGATE TASKS TABLE ──
-- Core delegation record. Each task = one delegated piece of work.

CREATE TABLE IF NOT EXISTS delegate_tasks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    created_by UUID REFERENCES firm_members(id),       -- delegating attorney
    assigned_to UUID REFERENCES firm_members(id),       -- receiving associate/staff
    
    -- Task details
    title TEXT NOT NULL,
    description TEXT,
    original_prompt TEXT,                                -- raw natural-language delegation
    
    -- Classification (populated by Aether Runtime)
    category TEXT CHECK (category IN (
        'MOTION', 'DISCOVERY', 'CLIENT_INTAKE', 'BILLING',
        'RESEARCH', 'FILING', 'CORRESPONDENCE', 'REVIEW',
        'CONTRACT', 'COMPLIANCE', 'OTHER'
    )),
    priority TEXT DEFAULT 'NORMAL' CHECK (priority IN ('URGENT', 'HIGH', 'NORMAL', 'LOW')),
    
    -- Status lifecycle
    status TEXT DEFAULT 'PENDING' CHECK (status IN (
        'PENDING', 'ASSIGNED', 'IN_PROGRESS', 'REVIEW', 'COMPLETE', 'BLOCKED', 'CANCELLED'
    )),
    
    -- Billing
    billable BOOLEAN DEFAULT true,
    estimated_hours DECIMAL(5,2),
    actual_hours DECIMAL(5,2) DEFAULT 0,
    matter_number TEXT,                                  -- law firm case/matter reference
    
    -- Privacy & Security
    confidential BOOLEAN DEFAULT false,                  -- triggers Compliance Vault route
    privilege_flag BOOLEAN DEFAULT false,                -- attorney-client privilege marker
    
    -- AI audit trail
    ai_classification JSONB DEFAULT '{}',                -- Aether Runtime classification output
    critic_review JSONB DEFAULT '{}',                    -- CriticGate audit trail
    
    -- Attachments & notes
    attachments JSONB DEFAULT '[]',
    notes JSONB DEFAULT '[]',                            -- [{author, text, timestamp}]
    
    -- Dates
    due_date TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tasks_firm ON delegate_tasks(firm_id);
CREATE INDEX idx_tasks_status ON delegate_tasks(status);
CREATE INDEX idx_tasks_assigned ON delegate_tasks(assigned_to);
CREATE INDEX idx_tasks_created_by ON delegate_tasks(created_by);
CREATE INDEX idx_tasks_category ON delegate_tasks(category);
CREATE INDEX idx_tasks_matter ON delegate_tasks(matter_number);
CREATE INDEX idx_tasks_due_date ON delegate_tasks(due_date);


-- ── 4. TASK ACTIVITY LOG ──
-- Immutable audit trail for every state change on a task.

CREATE TABLE IF NOT EXISTS task_activity (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES delegate_tasks(id) ON DELETE CASCADE,
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    actor_id UUID REFERENCES firm_members(id),
    action TEXT NOT NULL,                                 -- e.g., 'CREATED', 'ASSIGNED', 'STATUS_CHANGED', 'HOURS_LOGGED'
    old_value TEXT,
    new_value TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activity_task ON task_activity(task_id);
CREATE INDEX idx_activity_firm ON task_activity(firm_id);


-- ── 5. AUTO-UPDATE TRIGGER ──
-- Keeps updated_at current on delegate_tasks.

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_tasks_updated_at
    BEFORE UPDATE ON delegate_tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_firms_updated_at
    BEFORE UPDATE ON firms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ═══════════════════════════════════════════════════
--  ROW-LEVEL SECURITY (RLS)
--  Firm-level data isolation: users can ONLY see
--  data belonging to their own firm.
-- ═══════════════════════════════════════════════════

ALTER TABLE firms ENABLE ROW LEVEL SECURITY;
ALTER TABLE firm_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE delegate_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_activity ENABLE ROW LEVEL SECURITY;

-- Firms: members can only see their own firm
CREATE POLICY firms_select ON firms FOR SELECT USING (
    id IN (
        SELECT firm_id FROM firm_members WHERE user_id = auth.uid()
    )
);

-- Firm members: can see colleagues in same firm
CREATE POLICY members_select ON firm_members FOR SELECT USING (
    firm_id IN (
        SELECT firm_id FROM firm_members WHERE user_id = auth.uid()
    )
);

-- Tasks: full CRUD for same-firm members
CREATE POLICY tasks_select ON delegate_tasks FOR SELECT USING (
    firm_id IN (
        SELECT firm_id FROM firm_members WHERE user_id = auth.uid()
    )
);

CREATE POLICY tasks_insert ON delegate_tasks FOR INSERT WITH CHECK (
    firm_id IN (
        SELECT firm_id FROM firm_members WHERE user_id = auth.uid()
    )
);

CREATE POLICY tasks_update ON delegate_tasks FOR UPDATE USING (
    firm_id IN (
        SELECT firm_id FROM firm_members WHERE user_id = auth.uid()
    )
);

-- Activity log: read-only for same-firm members
CREATE POLICY activity_select ON task_activity FOR SELECT USING (
    firm_id IN (
        SELECT firm_id FROM firm_members WHERE user_id = auth.uid()
    )
);

-- Service role bypass for API/backend operations
CREATE POLICY firms_service ON firms FOR ALL USING (
    auth.role() = 'service_role'
);

CREATE POLICY members_service ON firm_members FOR ALL USING (
    auth.role() = 'service_role'
);

CREATE POLICY tasks_service ON delegate_tasks FOR ALL USING (
    auth.role() = 'service_role'
);

CREATE POLICY activity_service ON task_activity FOR ALL USING (
    auth.role() = 'service_role'
);


-- ═══════════════════════════════════════════════════
--  SEED DATA (Pilot Test Firm)
-- ═══════════════════════════════════════════════════

INSERT INTO firms (id, name, size, practice_areas, subscription_tier, seat_count, contact_email)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Antigravity Test Firm',
    'SMALL',
    ARRAY['General Practice', 'Technology Law'],
    'PILOT',
    5,
    'executive@antigravity.ai'
) ON CONFLICT (id) DO NOTHING;
