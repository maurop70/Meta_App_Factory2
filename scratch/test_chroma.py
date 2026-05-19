import sys

# Monkeypatch pydantic.v1 to handle Python 3.14 typing inference issues with chromadb config
try:
    import pydantic.v1.fields as pydantic_fields
    from typing import Any
    old_infer = pydantic_fields.ModelField.infer
    def new_infer(*args, **kwargs):
        try:
            return old_infer(*args, **kwargs)
        except Exception as e:
            # Catch type inference ConfigError and retry with Any annotation
            name = kwargs.get("name", "")
            # print(f"Type inference failed for {name}, falling back to Any")
            kwargs['annotation'] = Any
            try:
                return old_infer(*args, **kwargs)
            except Exception:
                raise e
    pydantic_fields.ModelField.infer = new_infer
    print("Successfully monkeypatched pydantic.v1 for Python 3.14 compatibility.")
except Exception as patch_err:
    print(f"Failed to monkeypatch pydantic: {patch_err}")

import chromadb
from pathlib import Path
import os

db_path = Path(os.getcwd()) / "vault" / "vector_store"
print(f"Testing ChromaDB PersistentClient at {db_path}...")
client = chromadb.PersistentClient(path=str(db_path))

collection = client.get_or_create_collection(
    name="architect_memory",
    metadata={"hnsw:space": "cosine"}
)

print("Collection created/retrieved successfully.")

# Let's try adding a small document
collection.add(
    documents=["Test memory payload"],
    metadatas=[{"agent": "CFO"}],
    ids=["test_1"]
)
print("Added test document.")

results = collection.query(
    query_texts=["test"],
    n_results=1
)
print("Query successful:", results)
