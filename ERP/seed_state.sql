BEGIN TRANSACTION;
CREATE TABLE erp_employees (id TEXT PRIMARY KEY, name TEXT, pin_code TEXT, authorization_level TEXT);
INSERT INTO "erp_employees" VALUES('EMP-999','Alpha Tech','1234','ADMIN');
INSERT INTO "erp_employees" VALUES('ADMIN-001','System Admin','1234','ADMIN');
CREATE TABLE erp_maintenance_logs (id TEXT PRIMARY KEY, reported_by TEXT, asset_id TEXT, issue_description TEXT, status TEXT, assigned_to TEXT, resolved_at TEXT, reported_at TEXT);
COMMIT;
