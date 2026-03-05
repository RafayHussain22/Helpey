# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Helpey is a web application where users authenticate via Google OAuth (Gmail only), and the app reads their Google Drive files to use as a knowledge base. An AI chatbot answers questions strictly based on the user's Drive content — no general knowledge responses.

## Architecture

Monorepo with `frontend/` and `backend/` directories.

### Frontend (`frontend/`)
- React 19 + Vite 7 (SPA, no SSR)
- TypeScript 5.9 strict mode
- Tailwind CSS v4, Radix UI primitives
- TanStack React Query v5 (server state), Zustand v5 (auth state)
- react-router v7 (createBrowserRouter)
- Brand: #C67F17 (primary), #FAFAF8 (background)
- Fonts: DM Sans (UI), JetBrains Mono (code/data)

### Backend (`backend/`)
- Python 3.12+, FastAPI >= 0.115, Uvicorn
- SQLAlchemy 2 (async with asyncpg), Alembic migrations
- Postgres (relational data), ChromaDB (vector store, embedded mode)
- Celery with SQLite broker (background tasks)
- PyJWT HS256 httpOnly cookie auth (7-day expiry)

### AI/ML
- Anthropic Claude Haiku (query classification), Claude Sonnet (answer synthesis + streaming + OCR)
- Google Gemini text-embedding-004 (768-dim embeddings)
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

## Key Decisions — Do NOT Change Without User Approval
- No OpenAI — embeddings use Google Gemini
- No Redis — Celery uses SQLite broker
- No pgvector — vectors stored in ChromaDB
- No cloud file storage — files stored locally in `backend/uploads/`
- Google OAuth only — no other auth methods
