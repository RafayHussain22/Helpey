# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Helpey is a web application where users authenticate via Google OAuth (Gmail only), and the app automatically ingests their entire Google Drive (including shared drives and "Shared with me") into a shared knowledge base. An AI chatbot answers questions based on documents the user has Google Drive permissions to access — no general knowledge responses.

Documents are stored in a shared pool: when any user syncs their Drive, those files become queryable by all users who have the appropriate Google Drive permissions (by email, domain, or "anyone" access). Same files synced by multiple users are deduplicated by `google_file_id`.

This is a PoC for a larger project involving one-time data migration of client data (Google Drive or Microsoft SharePoint).

## Architecture

Monorepo with `frontend/` and `backend/` directories.

### Frontend (`frontend/`)
- React 19 + Vite 7 (SPA, no SSR)
- TypeScript 5.9 strict mode
- Tailwind CSS v4, Radix UI primitives
- TanStack React Query v5 (server state), Zustand v5 (auth + chat state)
- react-router v7 (createBrowserRouter)
- Brand: #C67F17 (primary), #FAFAF8 (background)
- Fonts: DM Sans (UI), JetBrains Mono (code/data)
- Sync dashboard in sidebar (replaces old file picker) with real-time polling

### Backend (`backend/`)
- Python 3.12+, FastAPI >= 0.115, Uvicorn
- SQLAlchemy 2 (async with asyncpg), Alembic migrations
- Postgres (relational data), ChromaDB (vector store, embedded mode)
- Celery with SQLite broker (background tasks)
- PyJWT HS256 httpOnly cookie auth (7-day expiry)
- Auto-ingest: full Drive sync triggered on first login, with re-sync button for delta updates
- Sync task manages its own token refresh (no access_token passed as arg)
- SSE streaming runs sync LLM generators in thread executor to avoid blocking async event loop

### AI/ML
- Anthropic Claude Haiku (query classification), Claude Sonnet (answer synthesis + streaming + OCR)
- OpenAI text-embedding-3-small (1536-dim embeddings)
- Docling → PyMuPDF → Claude Vision (3-tier document parsing)
- Chonkie semantic chunking (potion-base-32M, 400-token target, 50-token overlap)

## Development Commands

### Backend
```bash
cd backend
uv sync                              # Install dependencies
uv run uvicorn app.main:app --reload  # Start dev server (port 8000)
uv run alembic upgrade head           # Run migrations
uv run celery -A app.tasks.celery_app worker --loglevel=info  # Start Celery worker
```

### Frontend
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Start dev server (port 5173, proxies /api → localhost:8000)
npm run build        # Production build
```

### Environment
- Backend config: `backend/.env.local` (see `backend/.env.example`)
- Vite dev proxy: `/api` → `localhost:8000`

## Drive Sync Flow
1. User logs in via Google OAuth → `google_callback` auto-triggers `sync_user_drive.delay(user_id)` if `initial_sync_done` is false
2. Celery task refreshes token internally, enumerates ALL Drive files (`corpora=allDrives`), diffs against shared document pool
3. New files (by `google_file_id`) → create Document rows → download → chain to `process_document` task
4. Existing files get permissions refreshed; modified files (by `modifiedTime`) → delete old chunks → re-download and re-process
4a. Duplicate files are deduplicated — if a file already exists in the pool, only permissions and `synced_by_user_id` are updated
5. Task sets `user.initial_sync_done = True` on completion
6. Frontend sidebar polls `GET /api/documents/sync/status` every 2s while `is_syncing` is true
7. Re-sync button triggers `POST /api/documents/sync` (no body) for delta sync
8. Failed files can be retried in bulk via `POST /api/documents/reprocess-failed`

## Key Decisions — Do NOT Change Without User Approval
- Embeddings use OpenAI, LLM uses Anthropic — no Google Gemini
- No Redis — Celery uses SQLite broker
- No cloud file storage — files stored locally in `backend/uploads/`
- Google OAuth only — no other auth methods
- Full Drive auto-ingest on login — no manual file picking
- Shared document pool — all synced files are accessible to any user with matching Google Drive permissions
- Documents use `synced_by_user_id` (nullable, SET NULL on user delete) instead of strict ownership
- Permission filtering via Google Drive permission objects stored in Document.permissions (JSONB)
