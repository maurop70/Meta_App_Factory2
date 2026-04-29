import sys

with open('maintenance_backend.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """def check_rate_limit(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)).isoformat()
        
        cursor.execute("DELETE FROM auth_rate_limits WHERE attempt_timestamp < ?", (cutoff,))
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) as attempt_count FROM auth_rate_limits WHERE employee_id = ?", (employee_id,))
        row = cursor.fetchone()
        
        if row and row['attempt_count'] >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Account locked.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error during rate limit verification: {e}")
        raise HTTPException(status_code=500, detail="Security boundary enforcement failed.")
    finally:
        conn.close()

def record_failed_attempt(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("INSERT INTO auth_rate_limits (employee_id, attempt_timestamp) VALUES (?, ?)", (employee_id, now))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to record authentication anomaly: {e}")
    finally:
        conn.close()

def clear_failed_attempts(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM auth_rate_limits WHERE employee_id = ?", (employee_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to clear rate limit ledger: {e}")
    finally:
        conn.close()"""

replacement = """def check_rate_limit(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = int(time.time())
        cutoff = now - (LOCKOUT_WINDOW_MINUTES * 60)
        
        # Bounded read to avoid DB lock thrashing under brute force
        cursor.execute("SELECT COUNT(*) as attempt_count FROM auth_rate_limits WHERE employee_id = ? AND attempt_timestamp > ?", (employee_id, cutoff))
        row = cursor.fetchone()
        
        if row and row['attempt_count'] >= MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Account locked.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error during rate limit verification: {e}")
        raise HTTPException(status_code=500, detail="Security boundary enforcement failed.")
    finally:
        conn.close()

def record_failed_attempt(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = int(time.time())
        cursor.execute("INSERT INTO auth_rate_limits (employee_id, attempt_timestamp) VALUES (?, ?)", (employee_id, now))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to record authentication anomaly: {e}")
    finally:
        conn.close()

def clear_failed_attempts(employee_id: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = int(time.time())
        cutoff = now - (LOCKOUT_WINDOW_MINUTES * 60)
        
        # Self-healing ledger pruning deferred to successful login
        cursor.execute("DELETE FROM auth_rate_limits WHERE attempt_timestamp < ?", (cutoff,))
        cursor.execute("DELETE FROM auth_rate_limits WHERE employee_id = ?", (employee_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to clear rate limit ledger: {e}")
    finally:
        conn.close()"""

# normalize line endings
content = content.replace('\r\n', '\n')
target = target.replace('\r\n', '\n')

if target in content:
    content = content.replace(target, replacement)
    with open('maintenance_backend.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Successfully replaced block.")
else:
    print("Error: Target block not found. Checking differences...")
    import difflib
    # just print that it failed
    sys.exit(1)
