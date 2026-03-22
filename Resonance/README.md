# Resonance — V3.2 (Socratic Tutor Release)

> Built by **Meta App Factory** — Antigravity AI  
> Last Updated: 2026-03-22

## Overview

Multi-agent educational app for teenagers with auditory processing challenges. Alex is a 17-year-old AI Wingman who provides holistic support: academic tutoring, social coaching, emotional validation, and structured learning.

## V3.2 Features

| Feature | Module | Status |
|---|---|---|
| Alex Chat (SSE Streaming) | `app_stream.py` | ✅ Active |
| Parent Portal | `server.py` | ✅ Active |
| Council of Therapists | `Sentinel_Bridge/council_engine.py` | ✅ Active |
| Clinical Intelligence Pipeline | `report_digest.py` | ✅ Active |
| **Socratic Tutor (Step-Gating)** | `.agent/workflows/Resonance-Socratic-Tutor.md` | ✅ NEW |
| **Aether Cognitive Layer** | `.agent/workflows/Aether-Cognitive-Layer.md` | ✅ NEW |
| **Gemini Vision OCR** | `server.py → _extract_text_via_gemini_vision()` | ✅ NEW |
| **Intelligent Model Router** | `model_router_v3.py` | ✅ NEW |
| **Graph Memory Engine** | `graph_memory_v3.py` | ✅ NEW |
| **Phantom QA Agent** | `Project_Aether/C-Suite_Active_Logic/Phantom_QA/` | ✅ NEW |
| Mind Map Generation (Mermaid) | `server.py → /api/study/mindmap` | ✅ Active |
| Conversation Mind Map | `server.py → /api/study/conversation-mindmap` | ✅ Active |
| File Upload (TXT/PDF/DOCX/PPTX) | `server.py → /api/upload` | ✅ Active |
| Progress Tracking & Streaks | `app_stream.py` | ✅ Active |

## Architecture

```
Resonance/
├── server.py                  # FastAPI backend (Port 5006)
├── app_stream.py              # SSE streaming + System Prompt + Model Router
├── model_router_v3.py         # Intelligent API gateway (Gemini/o3/Claude)
├── graph_memory_v3.py         # Aether cognitive node-edge memory
├── auto_heal.py               # V3 resilience layer
├── resonance_ui/              # Vite + React frontend (Port 5174)
├── Sentinel_Bridge/           # Council of Therapists engine
├── uploads/                   # File upload storage + OCR output
├── .Gemini_state/             # Persistent chat history
├── parent_config.json         # Parent Portal configuration
├── config.json                # App metadata
└── Launch_Resonance_V3.bat    # One-click launcher
```

## Channel Modes

| Channel | Purpose |
|---|---|
| `#general` | Casual teen chat, vocabulary reinforcement |
| `#wingman-mode` | Social simulation + Socratic Tutor (homework interception) |
| `#focus-room` | Structured learning, Teach-Back Loop, Academic Override |
| `#mixing-board` | Creative writing, language construction |

## Quick Start

```bash
# Option 1: One-click launcher
Launch_Resonance_V3.bat

# Option 2: Manual
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your API keys
uvicorn server:app --host 0.0.0.0 --port 5006
cd resonance_ui && npm run dev
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/chat/stream` | SSE chat streaming |
| POST | `/api/chat/clear` | Clear chat history |
| POST | `/api/upload` | File upload + OCR extraction |
| GET | `/api/uploads` | List uploaded files |
| POST | `/api/study/mindmap` | Generate mind map from document |
| POST | `/api/study/conversation-mindmap` | Generate mind map from chat |
| POST | `/api/study/summary` | Generate study summary |
| GET | `/api/health` | Health check |
| GET | `/api/parent/config` | Get parent configuration |
| POST | `/api/parent/config` | Update parent configuration |

## N8N Workflow Integration

| Workflow | ID | Purpose |
|---|---|---|
| MetaApp: Resonance | `IT4LuCQm7Ph62Hf2` | Primary chat webhook |
| Socratic Bridge | `leTQDufs38i9ZOyX` | Alpha Architect homework deconstruction |
| Aether Memory Synthesis | `UMyp1NbxN4wXXEnv` | Cognitive breakthrough logging |
| Aether Streak Monitor | `fg4OcUXycA6VjFvL` | Daily gamification cron |

## Testing

```bash
# Run Phantom QA regression test
python Project_Aether/C-Suite_Active_Logic/Phantom_QA/phantom_agent.py --app Resonance --persona leo_friend
```

---
*Last Updated: 2026-03-22 — V3.2 Socratic Tutor + Vision OCR + Phantom QA Release*
