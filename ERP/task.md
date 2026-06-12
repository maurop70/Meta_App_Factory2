# Task Checklist: Back Office Inventory Management Module

This checklist tracks the implementation of the Back Office Inventory Management Module. 
- **Developer (Claude Code):** Mark tasks as `[x]` when fully coded and verified.
- **Architect (Antigravity):** Will review code commits and sign off.

---

## Phase 1: Database Schema Migrations
- [x] Create migration script to create `erp_suppliers` table
- [x] Create migration script to create `erp_purchase_orders` table
- [x] Create migration script to create `erp_purchase_order_items` table
- [x] Create migration script to create `erp_inventory_manual_logs` table
- [x] Add `supplier_id` column to `erp_skus` and load seed data for default suppliers and categories (`CAT-ADMIN`)

## Phase 2: Backend REST APIs (FastAPI)
- [x] Implement `POST /api/inventory/manual-log` (manual Stock In/Out tracking)
- [x] Upgrade threshold evaluation worker to auto-group low-stock SKUs into supplier Draft POs
- [x] Implement HOD Draft PO endpoints:
  - [x] `GET /api/orders/drafts`
  - [x] `PUT /api/orders/{po_id}/update` (Update qty, notes, priority flag)
  - [x] `DELETE /api/orders/{po_id}/items/{sku_id}` (Exclude line item)
  - [x] `POST /api/orders/submit` (Submit POs to CFO)
- [x] Implement CFO Review & Actuation endpoints:
  - [x] `GET /api/orders/approvals` (Fetch pending queue, priority sorted)
  - [x] `POST /api/orders/actuate-bulk` (Approve / Hold / Reject)
  - [x] `POST /api/orders/{po_id}/receive` (HOD registers delivery and updates inventory levels)

## Phase 3: Transactional PO Email Integration
- [x] Create HTML/CSS Purchase Order email template with bold Delivery ETA block
- [x] Integrate SMTP/SendGrid dispatch hook when CFO approves an order

## Phase 4: Frontend UI Components (React + CSS)
- [x] Build Manual Inventory Log Widget (Stock-In/Out Toggle, search, comments)
- [x] Build HOD Workspace (Line-item deletes, High Priority pulse switch, ETA calendar override)
- [x] Build CFO Approvals Panel (Priority bubble-up, multi-select checkboxes for bulk operations)

## Phase 5: Verification & Verification
- [x] Run low-stock threshold trigger integration tests
- [x] Run CFO role-based access control (RBAC) verification tests
- [x] Perform manual end-to-end user experience audit
