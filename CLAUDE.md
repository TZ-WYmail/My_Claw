# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**LocalCommandCenter** — A FastAPI-based local gateway that receives GLM agent Tool Call requests and operates on the local system. Provides task management, secure downloading, file search, sandbox execution, and an AI chat interface.

## Common Commands

### Development Setup
```bash
cd local-gateway
conda activate claude
pip install -r requirements.txt
```

### Run the Application
```bash
# Start the gateway (requires Docker for sandbox features)
python main.py
# Service runs at http://localhost:8900

# With ngrok for external access
ngrok http 8900
```

### Testing
```bash
# Run all tests (requires server running on localhost:8900)
python -m pytest test/ -v

# Run specific test file
python -m pytest test/test_api.py -v
python -m pytest test/test_security.py -v
```

### Environment Variables
Key env vars defined in `config.py`:
- `GATEWAY_HOST` / `GATEWAY_PORT` — Server binding (default: 0.0.0.0:8900)
- `DOWNLOADS_DIR` — Download archive directory
- `SANDBOX_TIMEOUT` / `SANDBOX_MEMORY_LIMIT` — Docker sandbox limits
- `AI_API_BASE` / `AI_API_KEY` / `AI_MODEL` — AI chat configuration
- `CORS_ORIGINS` — CORS allowed origins

## Architecture

### Layer Structure (local-gateway/)
```
main.py              # FastAPI entry point, lifespan management, router registration
config.py            # Global settings, AIConfig class with JSON persistence
├── models/
│   └── schemas.py   # Pydantic models for 5 Tool schemas + dashboard/chat models
├── routers/         # HTTP endpoint handlers (thin, delegate to services)
│   ├── task_manager.py
│   ├── safe_downloader.py
│   ├── file_search.py
│   ├── sandbox_executor.py
│   ├── job_status.py
│   ├── chat.py      # AI chat with function calling
│   └── dashboard.py # Stats, logs, history endpoints
├── services/        # Business logic
│   ├── task_service.py      # SQLite CRUD + batch orchestration + scheduling
│   ├── download_service.py  # Async downloads + security scanning
│   ├── sandbox_service.py   # Docker SDK container management
│   ├── search_service.py    # Local file fuzzy search
│   ├── ai_service.py        # OpenAI/GLM API integration + tool routing
│   └── utils.py
└── static/          # Web UI (index.html, style.css, app.js)
```

### Key Design Patterns

**Router-Service Separation**: Routers in `routers/` handle HTTP concerns (request/response models) and delegate all business logic to `services/`. No business logic in routers.

**Async SQLite**: Uses `aiosqlite` for async database operations. Database path configured in `config.DB_PATH` (defaults to `data/tasks.db`).

**Job System**: Long-running operations (large downloads, sandbox execution) return immediately with a `job_id`. Clients poll `POST /api/job/status` to track progress. Job results stored in memory with TTL (`config.JOB_RESULT_TTL`).

**AI Function Calling**: `ai_service.py` implements an OpenAI-compatible function calling loop. The AI can invoke 5 tools: task_manager, safe_downloader, file_search, sandbox_executor, job_status. Tool definitions are in `ai_service.TOOLS`.

**AI Config Persistence**: `AIConfig` class in `config.py` supports runtime modification via `/api/chat/config` endpoints and persists to `data/ai_config.json`.

### Database Schema (SQLite)
Three main tables in `task_service.py`:
- `tasks` — Task management with recurrence support
- `download_history` — Download audit log
- `operation_logs` — General operation logging

### Sandbox Security
Docker-based isolation in `sandbox_service.py`:
- Images: python:3.11-slim, node:20-slim, linuxserver/ffmpeg, pandoc/core
- Timeout and memory limits enforced
- Dynamic file injection via temp volume mounts

## Copilot Instructions

This repo has caveman mode configured (`.github/copilot-instructions.md`). When user invokes "caveman mode" or `/caveman`, respond with ultra-compressed communication:
- Drop articles, filler words, pleasantries
- Pattern: [thing] [action] [reason]
- Levels: lite | full (default) | ultra | wenyan-lite | wenyan-full | wenyan-ultra
- Auto-clarity for security warnings and destructive operations
- Code/commits remain normal

## File Guidelines

- **Schemas**: All API request/response models in `models/schemas.py` — use strict Pydantic validation with `field_validator` for ISO 8601 dates
- **Task Time Handling**: `task_service.py` has `_normalize_time()` for flexible date parsing (supports "3月22日", "MM-DD", ISO formats)
- **Security**: `DANGEROUS_FILENAME_CHARS` and `EXECUTABLE_EXTENSIONS` checks in download flow
- **Static Files**: Web UI is vanilla JS/CSS in `static/` — no build step required
