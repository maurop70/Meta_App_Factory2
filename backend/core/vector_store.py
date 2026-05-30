import asyncio
import os
import chromadb
from typing import List, Dict, Any, Optional

class VectorStore:
    """
    Vector Store isolation layer wrapper for ChromaDB.
    STRICT GUARDRAIL: All disk I/O client methods are executed inside asyncio.to_thread
    to prevent blocking the main ASGI event loop.
    """
    def __init__(self, persist_directory: str = "./chroma_data"):
        self.persist_directory = os.path.abspath(persist_directory)
        os.makedirs(self.persist_directory, exist_ok=True)
        # Disk I/O client instantiation
        self.client = chromadb.PersistentClient(path=self.persist_directory)

    async def get_or_create_collection_async(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        return await asyncio.to_thread(self.client.get_or_create_collection, name=name, metadata=metadata)

    async def add_async(
        self,
        collection_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None
    ) -> None:
        """
        Adds vectors and documents asynchronously to the store.
        STRICT GUARDRAIL: Runs inside asyncio.to_thread.
        """
        collection = await self.get_or_create_collection_async(collection_name)
        await asyncio.to_thread(
            collection.add,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

    async def query_async(
        self,
        collection_name: str,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Queries vectors asynchronously from the store.
        STRICT GUARDRAIL: Runs inside asyncio.to_thread.
        """
        collection = await self.get_or_create_collection_async(collection_name)
        return await asyncio.to_thread(
            collection.query,
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            where_document=where_document
        )

    async def get_async(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Retrieves elements asynchronously from the store.
        STRICT GUARDRAIL: Runs inside asyncio.to_thread.
        """
        collection = await self.get_or_create_collection_async(collection_name)
        return await asyncio.to_thread(
            collection.get,
            ids=ids,
            where=where,
            limit=limit,
            offset=offset,
            where_document=where_document,
            include=include
        )
