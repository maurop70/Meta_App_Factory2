# Implementation Plan: Manufacturing ERP Traceability & Warehousing

This document outlines the implementation plan and database migrations for the next phase of the Manufacturing ERP system, integrating with the existing Maintenance Work Order (MWO) module.

## 1. Goal Description
The objective is to implement the database schemas and logistics flow for a modular, traceability-first manufacturing ERP. This system must track raw materials and packaging from supplier receipt, through storage, daily transfers to production line warehouses, and consumption/yield events on the production lines.

---

## 2. Database Schema Design (PostgreSQL / Supabase)

We will use the existing Supabase PostgreSQL instance:
`postgresql://postgres.mcznfhygdvnirxbisgzt:Gelatoshoppe1976!@aws-1-us-east-1.pooler.supabase.com:5432/postgres`

### 2.1 Schema Extensions
We will alter the existing `erp_skus` table:
```sql
ALTER TABLE erp_skus ADD COLUMN IF NOT EXISTS sku_type TEXT NOT NULL CHECK(sku_type IN ('RAW_MATERIAL', 'PACKAGING', 'BULK', 'FINISHED_GOOD', 'MAINTENANCE_PART'));
ALTER TABLE erp_skus ADD COLUMN IF NOT EXISTS unit_of_measure TEXT NOT NULL DEFAULT 'UNIT';
```

### 2.2 New Manufacturing & Traceability Tables
```sql
-- 1. Lot Registry
CREATE TABLE IF NOT EXISTS erp_lots (
    lot_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    sku_id TEXT NOT NULL REFERENCES erp_skus(sku_id),
    supplier_lot_number TEXT,
    parent_production_job_id UUID,
    expiry_date DATE,
    status TEXT NOT NULL CHECK(status IN ('QUARANTINE', 'RELEASED', 'REJECTED', 'HOLD')) DEFAULT 'QUARANTINE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Production Lines
CREATE TABLE IF NOT EXISTS production_lines (
    line_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- 3. Bill of Materials (BOM) / Recipes
CREATE TABLE IF NOT EXISTS erp_bom (
    bom_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    parent_sku_id TEXT NOT NULL REFERENCES erp_skus(sku_id),
    component_sku_id TEXT NOT NULL REFERENCES erp_skus(sku_id),
    standard_qty_per_unit REAL NOT NULL CHECK(standard_qty_per_unit > 0),
    UNIQUE(parent_sku_id, component_sku_id)
);

-- 4. Production Jobs / Runs
CREATE TABLE IF NOT EXISTS production_jobs (
    job_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    line_id UUID NOT NULL REFERENCES production_lines(line_id),
    target_sku_id TEXT NOT NULL REFERENCES erp_skus(sku_id),
    target_qty REAL NOT NULL CHECK(target_qty > 0),
    status TEXT NOT NULL CHECK(status IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')) DEFAULT 'SCHEDULED',
    scheduled_date DATE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    operator_id TEXT REFERENCES erp_employees(id)
);

-- 5. Universal Stock Ledger (Inventory Movements)
CREATE TABLE IF NOT EXISTS erp_stock_ledger (
    transaction_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    sku_id TEXT NOT NULL REFERENCES erp_skus(sku_id),
    lot_id UUID NOT NULL REFERENCES erp_lots(lot_id),
    from_location_id TEXT NOT NULL REFERENCES erp_locations(id),
    to_location_id TEXT NOT NULL REFERENCES erp_locations(id),
    quantity REAL NOT NULL CHECK(quantity > 0),
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('RECEIPT', 'TRANSFER', 'CONSUMPTION', 'PRODUCTION_YIELD', 'SALE', 'WASTE', 'ADJUSTMENT')),
    reference_type TEXT NOT NULL CHECK(reference_type IN ('PO', 'PRODUCTION_JOB', 'SO', 'MWO', 'MANUAL_ADJ')),
    reference_id TEXT NOT NULL, -- UUID/Text of the linked PO, Job, MWO, or SO
    performed_by TEXT REFERENCES erp_employees(id),
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 3. Location Mapping Matrix
Inventory transactions in `erp_stock_ledger` will refer to the following IDs in the `erp_locations` table:

| Location Name | `id` | Location Type | Description |
|---|---|---|---|
| External Supplier | `LOC-SUPPLIER` | `EXTERNAL` | Virtual source for PO receipts |
| Main Warehouse | `LOC-MAIN-WH` | `WAREHOUSE` | Primary storage area |
| Line 1 Warehouse | `LOC-L1-WH` | `LINE_WAREHOUSE` | Production Line 1 storage (staging area) |
| Line 1 Production | `LOC-L1-PROD` | `PRODUCTION_LINE` | Active WIP area on Production Line 1 |
| Waste Bins | `LOC-WASTE` | `WASTE` | Bins for scrapped materials/packaging |
| Customer Dispatch | `LOC-CUSTOMER` | `EXTERNAL` | Virtual sink for Sales Order delivery |

---

## 4. Phase-by-Phase Execution Plan

### Phase 2: Schema Migration & Seeding (Current Step)
1. **Migration Script**: Create a script `migration_erp_v3.py` to connect to the Supabase Postgres instance and deploy the database schema extensions and new tables.
2. **Seeding Master Data**: Seed standard SKUs (e.g., Raw Materials: Milk, Sugar; Packaging: Cups, Lids; Bulks: Liquid Ice Cream Base; Finished Goods: Vanilla Pint) and link them to suppliers. Seed standard locations.

### Phase 3: Logistics & Inventory Flow
1. **Receiving Interface (Main Warehouse)**:
   * Screen for logistics staff to select an approved Purchase Order.
   * Input/auto-generate an internal Lot Code (e.g., `LOT-YYYYMMDD-[SEQ]`).
   * Capture supplier lot codes and expiry dates.
   * Write receipt transaction in `erp_stock_ledger` (`LOC-SUPPLIER` -> `LOC-MAIN-WH`).
2. **Warehouse Transfer Interface**:
   * Screen for transferring lots from Main Warehouse to Line-specific Warehouses (e.g., `LOC-MAIN-WH` -> `LOC-L1-WH`).
   * Validate that the lot exists and has sufficient quantity using ledger aggregation.
   * Record transfer transaction in `erp_stock_ledger`.

### Phase 4: Production & Bulk Execution (Future Step)
1. **Production WIP Feed**: Interface to deliver materials from Line Warehouses into the Production Line WIP location (`LOC-L1-WH` -> `LOC-L1-PROD`).
2. **Execution & Yield Screen**:
   * Line operators start production jobs.
   * Log the exact consumed raw material/bulk Lot IDs (writing `CONSUMPTION` ledger events).
   * Yield new Finished Good/Bulk Lot IDs (writing `PRODUCTION_YIELD` events).
   * Record scrap/damage (writing `WASTE` events to `LOC-WASTE`).

---

## 5. Verification Plan

### Automated Database Verification
- Run a test script to perform mock inventory receipts, transfers, and consumption.
- Query SQL to verify the balance of inventory by location:
  ```sql
  SELECT sku_id, lot_id, SUM(quantity) as balance
  FROM (
      SELECT sku_id, lot_id, quantity FROM erp_stock_ledger WHERE to_location_id = 'LOC-MAIN-WH'
      UNION ALL
      SELECT sku_id, lot_id, -quantity FROM erp_stock_ledger WHERE from_location_id = 'LOC-MAIN-WH'
  ) GROUP BY sku_id, lot_id;
  ```

### Manual Verification
- Deploy UI and verify that operators can receive PO items and transfer them to line warehouses with correct lot tracking.
