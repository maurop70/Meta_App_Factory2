import chromadb
from chromadb.utils import embedding_functions
import os

class ChromaMemory:
    """
    Skill for the Analyst Persona.
    Manages a local ChromaDB instance for RAG (Retrieval Augmented Generation).
    """
    def __init__(self, project_name="Global_Memory", persist_directory=None):
        if persist_directory is None:
            # Base directory for all projects (Relative to this skill file)
            SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.abspath(os.path.join(SKILLS_DIR, "..", "Meta_App_Factory", "Adv_Autonomous_Agent", "Projects"))
            persist_directory = os.path.join(base_dir, project_name, "data", "chroma")
        
        os.makedirs(persist_directory, exist_ok=True)
        print(f"--- ChromaMemory: Loading Isolated Memory for '{project_name}' ---", flush=True)
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        # Scope the collection name to the project to ensure total isolation
        self.collection = self.client.get_or_create_collection(
            name=f"memory_{project_name}",
            embedding_function=self.embedding_fn
        )

    def add_document(self, text, metadata=None, doc_id=None):
        """Adds a document to the vector store."""
        if doc_id is None:
            import hashlib
            doc_id = hashlib.md5(text.encode()).hexdigest()
        
        self.collection.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id]
        )
        return doc_id

    def ingest_folder(self, folder_path):
        """Scans a folder for documents and indexes them."""
        print(f"--- ChromaMemory: Ingesting knowledge from {folder_path} ---", flush=True)
        count = 0
        if not os.path.exists(folder_path):
            return 0

        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                text = ""
                
                # Simple TXT extraction
                if file.endswith(".txt"):
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                
                # Basic PDF extraction (requires pypdf logic if needed, but we'll start with text/markdown)
                elif file.endswith(".md"):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()

                if text.strip():
                    self.add_document(text, {"source": file, "path": file_path})
                    count += 1
        
        print(f"--- ChromaMemory: Successfully indexed {count} documents. ---", flush=True)
        return count

    def query(self, query_text, n_results=3):
        """Searches the memory for relevant snippets."""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results

if __name__ == "__main__":
    # Internal test
    mem = ChromaMemory("./data/test_chroma")
    mem.add_document("The CEO approved a 3-year growth plan.", {"type": "strategy"})
    results = mem.query("What did the CEO approve?")
    print(f"Query Results: {results['documents']}")
