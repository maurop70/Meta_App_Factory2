async def fetch_history(session_id: str, limit: int = 50, offset: int = 0) -> dict:
    """Async read operation for fetching chat history with strict pagination bounds."""
    await _init_db()
    
    def execute_read():
        with sqlite3.connect(DB_PATH, timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row
            
            # Parallel execution (mathematically bounded)
            count_cursor = conn.execute(
                "SELECT COUNT(*) as total FROM chat_history WHERE session_id = ?",
                (session_id,)
            )
            total = count_cursor.fetchone()["total"]
            
            # Enforced limit and offset natively at the SQLite execution layer
            cursor = conn.execute(
                "SELECT role, content, created_at FROM chat_history WHERE session_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", 
                (session_id, limit, offset)
            )
            items = [dict(row) for row in cursor.fetchall()]
            
            return {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset
            }
            
    return await asyncio.to_thread(execute_read)
