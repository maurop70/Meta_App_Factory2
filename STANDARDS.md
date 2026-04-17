# Meta App Factory Architectural Standards
# Version: 1.0.0 (V3 Hardened)
# Authority: Maintenance V3 Core Deployment

## 1. Explicit Relationship Mapping (MANDATORY)
To prevent `PGRST201` (ambiguous join) errors in Supabase/Postgrest, ALL queries that embed related tables MUST explicitly define the foreign key relationship.

### Correct Syntax
```python
# Explicitly name the FK column after the table name with an exclamation mark
supabase.table("work_orders").select("*, departments!department_ref_id(*)")
supabase.table("app_users").select("*, roles!role_id(*)")
```

### Forbidden Syntax
```python
# Ambiguous - will fail if multiple FKs exist between tables
supabase.table("work_orders").select("*, departments(*)")
```

## 2. Role Identity Normalization
Personnel must be linked to roles via `role_id` (UUID). Text-based role lookups are deprecated.

## 3. Native Event Dispatching
High-priority alerts must use the `app_notifications` SQL ledger for persistence and auditability. Avoid external dependencies (e.g., n8n) for core state-change notifications.

## 4. Work Order Traceability
Every status change must be logged to `work_order_history` with the `user_id` and a mandatory `note`.
