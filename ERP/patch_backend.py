import re

with open('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/maintenance_backend.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add openpyxl to imports
if 'import openpyxl' not in content:
    content = content.replace('import os\n', 'import os\nimport openpyxl\nfrom openpyxl.worksheet.datavalidation import DataValidation\n')

# Find get_departments to insert taxonomy endpoints
taxonomy_code = """
@app.get("/api/admin/lookups/locations")
def get_locations(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    jwt_payload: dict = Depends(verify_jwt_token)
):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM erp_locations ORDER BY name LIMIT ? OFFSET ?", (limit, offset))
        return {"data": [dict(r) for r in cursor.fetchall()]}
    finally:
        conn.close()

@app.post("/api/admin/ingest/department")
def ingest_department(payload: dict = Body(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
    name = payload.get("name")
    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Invalid department name")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        import uuid
        new_id = f"DEP-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("INSERT INTO erp_departments (id, name) VALUES (?, ?)", (new_id, name))
        conn.commit()
        return {"status": "success", "id": new_id, "name": name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Department already exists")
    finally:
        conn.close()

@app.post("/api/admin/ingest/location")
def ingest_location(payload: dict = Body(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
    name = payload.get("name")
    if not name or len(name) < 2:
        raise HTTPException(status_code=400, detail="Invalid location name")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        import uuid
        new_id = f"LOC-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("INSERT INTO erp_locations (id, name) VALUES (?, ?)", (new_id, name))
        conn.commit()
        return {"status": "success", "id": new_id, "name": name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Location already exists")
    finally:
        conn.close()

"""
if 'def get_locations(' not in content:
    content = content.replace('def get_departments(', taxonomy_code + 'def get_departments(')

# Add generate_xlsx_template utility
xlsx_utils = """
def generate_xlsx_template(headers, template_name, categories=[], departments=[], locations=[], hms=[], techs=[]):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ingestion_Template"
    
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_idx, value=header)
        
    lookup_ws = wb.create_sheet(title="_Lookups")
    lookup_ws.sheet_state = 'hidden'
    
    current_col = 1
    def add_lookup_col(name, items):
        nonlocal current_col
        lookup_ws.cell(row=1, column=current_col, value=name)
        for r_idx, item in enumerate(items, 2):
            lookup_ws.cell(row=r_idx, column=current_col, value=item)
        col_letter = openpyxl.utils.get_column_letter(current_col)
        formula = f"=_Lookups!${col_letter}$2:${col_letter}${len(items)+1 if len(items)>0 else 2}"
        current_col += 1
        return formula

    if "category_name" in headers and categories:
        form = add_lookup_col("Categories", categories)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("category_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "department_name" in headers and departments:
        form = add_lookup_col("Departments", departments)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("department_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "location" in headers and locations:
        form = add_lookup_col("Locations", locations)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("location") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "hm_name" in headers and hms:
        form = add_lookup_col("HMs", hms)
        dv = DataValidation(type="list", formula1=form, allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("hm_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "reports_to_hm_name" in headers and hms:
        form = add_lookup_col("HMs", hms)
        dv = DataValidation(type="list", formula1=form, allow_blank=True)
        col_letter = openpyxl.utils.get_column_letter(headers.index("reports_to_hm_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "tech_name" in headers and techs:
        form = add_lookup_col("Techs", techs)
        dv = DataValidation(type="list", formula1=form, allow_blank=True)
        col_letter = openpyxl.utils.get_column_letter(headers.index("tech_name") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)
        
    if "status" in headers:
        dv = DataValidation(type="list", formula1='"ACTIVE,DEGRADED,OFFLINE"', allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("status") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)

    if "role" in headers:
        dv = DataValidation(type="list", formula1='"ADMINISTRATOR,ADMIN,HM,TECH"', allow_blank=False)
        col_letter = openpyxl.utils.get_column_letter(headers.index("role") + 1)
        dv.add(f"{col_letter}2:{col_letter}1048576")
        ws.add_data_validation(dv)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={template_name}.xlsx"}
    )
"""

if 'def generate_xlsx_template' not in content:
    content = content.replace('# [PHASE 35.1.1]', xlsx_utils + '\n# [PHASE 35.1.1]')

# Update bulk equipment ingestion
old_bulk_equipment = """@app.get("/api/admin/ingest/equipment/template")
def get_equipment_ingestion_template(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["nomenclature", "category_name", "status", "department_name", "location", "hm_name", "tech_name"])
    
    # Adding a dummy row as an example
    writer.writerow(["Boiler System B", "HVAC", "ACTIVE", "Maintenance", "Main Warehouse", "John Smith", ""])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=equipment_ingestion_template.csv"}
    )

@app.post("/api/admin/ingest/equipment/bulk")
async def bulk_ingest_equipment(file: UploadFile = File(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a CSV file.")
        
    content = await file.read()
    try:
        decoded_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")
        
    reader = csv.DictReader(io.StringIO(decoded_content))
    expected_fields = {"nomenclature", "category_name", "status", "department_name", "location", "hm_name"}
    
    if not reader.fieldnames or not expected_fields.issubset(set(reader.fieldnames)):
        raise HTTPException(status_code=400, detail=f"Invalid CSV structure. Expected minimum headers: {', '.join(expected_fields)}")
        
    rows = list(reader)"""

new_bulk_equipment = """@app.get("/api/admin/ingest/equipment/template")
def get_equipment_ingestion_template(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN", "HM"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM erp_categories")
        categories = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_departments")
        departments = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_locations")
        locations = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_employees WHERE role='HM'")
        hms = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_employees WHERE role='TECH' OR authorization_level='TECHNICIAN'")
        techs = [row['name'] for row in c.fetchall()]
    finally:
        conn.close()
        
    headers = ["nomenclature", "category_name", "status", "department_name", "location", "hm_name", "tech_name"]
    return generate_xlsx_template(headers, "equipment_ingestion_template", categories, departments, locations, hms, techs)

@app.post("/api/admin/ingest/equipment/bulk")
async def bulk_ingest_equipment(file: UploadFile = File(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation: Administrative clearance required.")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an XLSX file.")
        
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        ws = wb.active
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        if not header_row: raise ValueError("Empty file")
        expected_fields = {"nomenclature", "category_name", "status", "department_name", "location", "hm_name"}
        if not expected_fields.issubset(set(header_row)):
            raise HTTPException(status_code=400, detail=f"Invalid XLSX structure. Expected minimum headers: {', '.join(expected_fields)}")
        rows = []
        for row_values in ws.iter_rows(min_row=2, values_only=True):
            if not any(row_values): continue
            row_dict = dict(zip(header_row, row_values))
            rows.append(row_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read XLSX: {e}")"""

if old_bulk_equipment in content:
    content = content.replace(old_bulk_equipment, new_bulk_equipment)
    
# Wait, row values need to be cast to string properly.
content = content.replace("row_data = {k.strip(): v.strip() if v else None for k, v in row.items()}", "row_data = {k.strip(): str(v).strip() if v is not None else None for k, v in row.items()}")

# Add Personnel and Part bulk endpoints
personnel_part_bulk_code = """
# Personnel Bulk
@app.get("/api/admin/ingest/personnel/template")
def get_personnel_ingestion_template(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM erp_departments")
        departments = [row['name'] for row in c.fetchall()]
        c.execute("SELECT name FROM erp_employees WHERE role='HM'")
        hms = [row['name'] for row in c.fetchall()]
    finally:
        conn.close()
        
    headers = ["name", "role", "pin_code", "department_name", "reports_to_hm_name"]
    return generate_xlsx_template(headers, "personnel_ingestion_template", departments=departments, hms=hms)

@app.post("/api/admin/ingest/personnel/bulk")
async def bulk_ingest_personnel(file: UploadFile = File(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Invalid file format.")
        
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        ws = wb.active
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        rows = []
        for row_values in ws.iter_rows(min_row=2, values_only=True):
            if not any(row_values): continue
            row_dict = dict(zip(header_row, row_values))
            rows.append(row_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read XLSX: {e}")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        cursor.execute("SELECT id, name FROM erp_departments")
        dep_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}
        
        cursor.execute("SELECT id, name FROM erp_employees WHERE role = 'HM'")
        hm_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}

        cursor.execute("BEGIN TRANSACTION")
        
        import bcrypt
        inserted_count = 0
        for i, row in enumerate(rows):
            row_data = {k.strip(): str(v).strip() if v is not None else None for k, v in row.items()}
            
            name = row_data.get('name')
            prole = row_data.get('role', '').upper()
            pin = row_data.get('pin_code')
            if not name or not prole or not pin:
                raise ValueError(f"Row {i+2}: Missing required fields.")
                
            dep_name = row_data.get('department_name')
            if not dep_name or dep_name.lower() not in dep_map:
                raise ValueError(f"Row {i+2}: Unknown Department Name '{dep_name}'")
            dep_id = dep_map[dep_name.lower()]
            
            hm_name = row_data.get('reports_to_hm_name')
            hm_id = None
            if hm_name:
                if hm_name.lower() not in hm_map:
                    raise ValueError(f"Row {i+2}: Unknown HM Name '{hm_name}'")
                hm_id = hm_map[hm_name.lower()]
                
            if prole in ['TECH', 'TECHNICIAN'] and not hm_id:
                raise ValueError(f"Row {i+2}: TECH must have a reports_to_hm_name")

            pin_hash = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            new_id = f"U-{uuid.uuid4().hex[:6].upper()}"
            
            cursor.execute(
                "INSERT INTO erp_employees (id, name, role, pin_hash, is_active, department_id, reports_to_hm_id) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (new_id, name, prole, pin_hash, dep_id, hm_id)
            )
            inserted_count += 1
            
        conn.commit()
        return {"status": "success", "message": f"Successfully ingested {inserted_count} personnel."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# Parts Bulk
@app.get("/api/admin/ingest/part/template")
def get_part_ingestion_template(jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation.")
    
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT name FROM erp_categories")
        categories = [row['name'] for row in c.fetchall()]
    finally:
        conn.close()
        
    headers = ["nomenclature", "category_name", "quantity_on_hand", "reorder_threshold", "unit_cost"]
    return generate_xlsx_template(headers, "part_ingestion_template", categories=categories)

@app.post("/api/admin/ingest/part/bulk")
async def bulk_ingest_part(file: UploadFile = File(...), jwt_payload: dict = Depends(verify_jwt_token)):
    role = jwt_payload.get("role")
    if role not in ["ADMINISTRATOR", "ADMIN"]:
        raise HTTPException(status_code=403, detail="RBAC Violation")
        
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Invalid file format.")
        
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
        ws = wb.active
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        rows = []
        for row_values in ws.iter_rows(min_row=2, values_only=True):
            if not any(row_values): continue
            row_dict = dict(zip(header_row, row_values))
            rows.append(row_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read XLSX: {e}")
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        cursor.execute("SELECT id, name FROM erp_categories")
        cat_map = {row['name'].lower().strip(): row['id'] for row in cursor.fetchall()}

        cursor.execute("BEGIN TRANSACTION")
        
        inserted_count = 0
        for i, row in enumerate(rows):
            row_data = {k.strip(): str(v).strip() if v is not None else None for k, v in row.items()}
            
            cat_name = row_data.get('category_name')
            if not cat_name or cat_name.lower() not in cat_map:
                raise ValueError(f"Row {i+2}: Unknown Category Name '{cat_name}'")
            cat_id = cat_map[cat_name.lower()]

            new_id = f"PRT-{uuid.uuid4().hex[:6].upper()}"
            
            cursor.execute(
                "INSERT INTO erp_parts (part_id, nomenclature, category_id, quantity_on_hand, reorder_threshold, unit_cost) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id, row_data.get('nomenclature'), cat_id, int(row_data.get('quantity_on_hand', 0)), int(row_data.get('reorder_threshold', 5)), float(row_data.get('unit_cost', 0.0)))
            )
            inserted_count += 1
            
        conn.commit()
        return {"status": "success", "message": f"Successfully ingested {inserted_count} parts."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
"""

if 'def get_personnel_ingestion_template' not in content:
    content += "\n" + personnel_part_bulk_code

with open('C:/Dev/Antigravity_AI_Agents/Meta_App_Factory/ERP/Maintenance_Work_Order/maintenance_backend.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied")
