import os
import sys
from pathlib import Path

# =====================================================================
# Pydantic v1 Python 3.14 Compatibility Hotfix
# Ensures chromadb can be imported without type inference ConfigErrors
# =====================================================================
try:
    import pydantic.v1.fields as pydantic_fields
    from typing import Any
    old_infer = pydantic_fields.ModelField.infer
    def new_infer(*args, **kwargs):
        try:
            return old_infer(*args, **kwargs)
        except Exception as e:
            # Fall back to Any annotation if Pydantic v1 fails to infer the type
            kwargs['annotation'] = Any
            try:
                return old_infer(*args, **kwargs)
            except Exception:
                raise e
    pydantic_fields.ModelField.infer = new_infer
except Exception:
    pass

import chromadb
from chromadb.config import Settings

class VectorMemoryMatrix:
    def __init__(self):
        # Strict local persistent storage. 
        # Physical disk mutation confined to the secure vault directory.
        db_path = Path(__file__).parent / "vault" / "vector_store"
        self.client = chromadb.PersistentClient(path=str(db_path))
        
        # Enforce exact collection schema
        self.collection = self.client.get_or_create_collection(
            name="architect_memory",
            metadata={"hnsw:space": "cosine"}
        )

    def lock_memory(self, session_id: str, payload: str, metadata: dict):
        self.collection.add(
            documents=[payload],
            metadatas=[metadata],
            ids=[f"{session_id}_{os.urandom(4).hex()}"]
        )

    def retrieve_context(self, query: str, n_results: int = 3):
        # Similarity search executed strictly before codebase generation
        return self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
