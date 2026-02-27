# TECHNICAL ARCHITECTURE

The **Elite Consulting Suite** uses a high-fidelity 'Cloud-to-Local' Bridge architecture.

## 1. Interaction Layer (Python/Tkinter)

- **CEO Point of Contact**: The user interacts with a consolidated interface.
- **Bridge.py**: Orchestrates the communication between the UI and the N8N cloud executor.

## 2. Execution Engine (N8N)

- **Elite Council Blueprint**: A multi-agent orchestration workflow.
- **Council of 7 Personas**: CEO, CMO, CFO, Product, Creative (Presentation Architect), Critic, and Analyst.
- **Tool Loop Logic**: Agents autonomously decide when to use live search (Tavily), vector memory (ChromaDB), or document management (Google Workspace).

## 3. Intelligence Layers

- **Live Search**: Integrated via Tavily API for real-time market research.
- **Vector Storage**: Local ChromaDB instance for project-isolated long-term memory.
- **Living Documents**: Direct integration with Google Slides/Sheets/Docs for persistent asset management.

## 4. Security & Isolation

- **Project Partitioning**: Every project (e.g., 'Project Neptune') has its own isolated directory and vector collection, ensuring enterprise-grade data security.
