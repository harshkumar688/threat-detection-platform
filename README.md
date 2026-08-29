# Threat Detection Platform

AI-based real-time threat (weapon) detection platform. Uses a YOLO-based computer vision pipeline to detect weapons in video feeds, tracks and verifies detections across frames to reduce false positives, computes an explainable risk score, and surfaces confirmed incidents to security operators through a FastAPI backend and a React dashboard.

> ⚠️ **Framing note:** This system detects and prioritizes *observable* threats (e.g., a visible weapon) for human review. It does **not** predict crime, infer intent, or perform facial recognition/identity inference of any kind. See [Privacy](#privacy--data-handling) below.

🚧 **This project is under active development.** Some modules are complete and tested; others are scaffolded but not yet implemented. See [Current Development Status](#current-development-status) for an honest breakdown.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Docker Setup](#docker-setup)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [API Documentation](#api-documentation)
- [Privacy & Data Handling](#privacy--data-handling)
- [Current Development Status](#current-development-status)
- [Roadmap](#roadmap)

---

## Problem Statement

Manual monitoring of CCTV/security feeds for weapons and threats is slow, error-prone, and doesn't scale. This platform automates weapon detection in video streams, applies temporal verification to suppress single-frame false alarms, scores the resulting incident by risk, and routes it to human operators for review, acknowledgement, and evidence-backed response — with role-based access control and audit logging throughout.

## Key Features

- **AI weapon detection** — configurable YOLO-based detector (image, video, webcam input)
- **Object tracking** — stable track IDs across frames, handles temporary detection loss
- **Temporal verification** — N/M sliding-window confirmation state machine to reduce false alerts
- **Explainable risk scoring** — 0–100 score with LOW/MEDIUM/HIGH/CRITICAL levels, fully transparent rule-based breakdown (no black-box logic)
- **Incident management** — full lifecycle (OPEN → ACKNOWLEDGED → RESOLVED/FALSE_POSITIVE) with audit trail
- **Evidence capture** — snapshot capture, secure storage (path-traversal safe), configurable retention
- **Optional privacy-preserving processing** — face blur/pixelation at evidence-capture time (localization only, no facial recognition)
- **Alerting** — configurable severity thresholds, pluggable notification providers (console/webhook/email), retry + dedup
- **Camera & location management** — register cameras, link to physical locations, incidents snapshot location at creation time
- **Authentication & RBAC** — JWT auth, bcrypt hashing, account lockout, ADMIN/OPERATOR/VIEWER roles, audit logging
- **Analytics dashboard** — real backend-driven charts (incidents over time, risk distribution, camera-wise breakdown, etc.) — no fabricated data
- **React dashboard** — Login, Live Monitoring, Incidents, Evidence, Cameras, Analytics, Users, Settings

## Architecture

```
                    ┌─────────────────┐
                    │  React Frontend │
                    │  (dashboard)    │
                    └────────┬────────┘
                             │ REST (JWT)
                    ┌────────▼────────┐
                    │  FastAPI Backend│
                    │  (auth, RBAC,   │
                    │  incidents,     │
                    │  evidence,      │
                    │  alerts, etc.)  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼──────┐    ┌────────▼────────┐   ┌───────▼───────┐
│  Detection   │    │   PostgreSQL /  │   │   Evidence    │
│  Service     │    │   Redis         │   │   Storage     │
│  (YOLO,      │    │  (repository    │   │  (filesystem, │
│  tracking,   │    │   pattern; in-  │   │   isolated    │
│  scoring)    │    │   memory today) │   │   from web)   │
└──────────────┘    └─────────────────┘   └───────────────┘
```

The backend currently uses an in-memory repository pattern behind abstract interfaces (Docker/PostgreSQL/Redis are not required to run and test the API locally) — a SQLAlchemy-backed implementation can be dropped in later without changing service or router code.

## Tech Stack

| Layer | Technology |
|---|---|
| AI / Detection | Python, PyTorch, Ultralytics YOLO, OpenCV |
| Backend | FastAPI, Pydantic, SQLAlchemy, Alembic, JWT (python-jose), bcrypt |
| Database (planned) | PostgreSQL 15, Redis 7 |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| Testing | pytest, pytest-asyncio, httpx |
| Deployment | Docker, Docker Compose, Nginx |

## Project Structure

```
threat-detection-platform/
├── backend/            # FastAPI application
│   ├── app/
│   │   ├── api/v1/     # Route handlers (auth, cameras, incidents, evidence, alerts, analytics...)
│   │   ├── auth/        # AuthService, RBAC permission matrix, audit log
│   │   ├── cameras/     # Camera & Location domain + services
│   │   ├── incidents/   # Incident lifecycle domain + services
│   │   ├── evidence/    # Evidence capture, storage, retention, audit log
│   │   ├── alerts/      # Alert dispatch + notification providers
│   │   ├── privacy/     # Optional face anonymization (evidence capture)
│   │   └── analytics/   # Real-data analytics service
│   └── tests/           # 368+ tests (unit + HTTP integration)
├── detection/           # AI/ML detection service (YOLO, tracking, scoring, verification)
├── frontend/            # React + TypeScript dashboard
├── training/             # Model training pipeline (dataset validation, eval, benchmarking)
├── config/               # nginx / postgres / redis configuration
├── scripts/              # Setup and utility scripts
└── docker-compose.yml
```

## Getting Started

### Backend Setup

```powershell
cd threat-detection-platform/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`, interactive docs at `http://localhost:8000/docs`.

### Frontend Setup

```bash
cd threat-detection-platform/frontend
npm install
npm run dev
```

Dashboard available at `http://localhost:3000` (or the port Vite reports).

### Docker Setup

```bash
cd threat-detection-platform
copy .env.example .env    # Windows; use `cp` on Linux/Mac
docker-compose up -d
```

## Environment Variables

Copy `threat-detection-platform/.env.example` to `.env` and fill in real values before deploying anywhere beyond local development. Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL`, `POSTGRES_*` | PostgreSQL connection |
| `REDIS_URL` | Redis connection |
| `JWT_SECRET_KEY` | Token signing — **must** be changed in any non-local environment |
| `CORS_ORIGINS` | Allowed frontend origins |
| `EVIDENCE_STORAGE_PATH`, `EVIDENCE_RETENTION_DAYS` | Evidence storage config |
| `PRIVACY_MODE` | `off` / `face_blur` / `face_pixelate` — optional evidence anonymization |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_FULL_NAME` | Seeded admin account (change the password before any shared deployment) |

`.env` is git-ignored and never committed. Never commit real secrets — only `.env.example` (placeholders) is tracked.

## Testing

```powershell
cd threat-detection-platform/backend
.\venv\Scripts\Activate.ps1
pytest tests/ -v
```

Current backend suite: **368 tests passing** (unit + HTTP-level integration tests covering auth, RBAC, cameras, locations, incidents, evidence, alerts, analytics, and privacy).

```powershell
cd threat-detection-platform/detection
python -m pytest tests/ -v
```

Detection module suite: **163 tests passing** (detection, tracking, scoring, verification, privacy).

## API Documentation

Auto-generated OpenAPI docs are served by the running backend:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Raw schema: `http://localhost:8000/openapi.json`

## Privacy & Data Handling

- Evidence capture supports an **optional** privacy mode (`PRIVACY_MODE=face_blur` or `face_pixelate`) that anonymizes detected face regions **before** the frame is ever written to storage — there is no unblurred copy retained once enabled.
- Face processing is **localization only** (OpenCV Haar-cascade), never recognition, embeddings, or identity inference. This is a hard boundary, not a "not yet implemented" gap.
- Evidence file downloads are restricted by role (admin/operator only); all evidence access (list views, downloads, denied attempts) is recorded in an append-only audit log.
- Evidence retention is configurable per privacy mode via `EVIDENCE_RETENTION_DAYS` / `EVIDENCE_RETENTION_DAYS_BY_PRIVACY_MODE`.
- Known limitation: Haar-cascade face detection can miss non-frontal, poorly lit, occluded, or very small faces — documented via the `/api/v1/evidence/privacy/status` endpoint, not hidden.

## Current Development Status

**✅ Implemented and tested:**
- AI detection module (YOLO inference, image/video/webcam)
- Object tracking (stable track IDs, lost/new track handling)
- Temporal verification (N/M confirmation state machine)
- Risk scoring engine (explainable, config-driven)
- Incident management (lifecycle, audit log)
- Evidence capture subsystem (secure storage, retention)
- Privacy-preserving evidence capture (face blur/pixelate)
- Authentication & RBAC (JWT, bcrypt, lockout, audit log)
- Camera & Location management (CRUD, incident linkage)
- Alert management (thresholds, providers, dedup, acknowledgement)
- Analytics (real database-driven metrics, no fabricated numbers)
- React dashboard: Login, Dashboard, Live Monitoring, Incidents, Incident Detail, Evidence, Cameras, Analytics, Users, Settings

**🚧 Under Development / Not Yet Implemented:**
- PostgreSQL/Redis are wired via an abstract repository pattern but currently run **in-memory** — a real SQLAlchemy-backed implementation is not yet connected
- WebSocket live feed / real-time alert push (`backend/app/websocket/`) — scaffolded, not implemented
- Some `backend/app/services/*` and `backend/app/models/*` files are placeholder stubs from initial scaffolding, superseded by the domain modules under `app/auth/`, `app/cameras/`, `app/incidents/`, `app/evidence/`, `app/alerts/` — pending cleanup
- Model training has a working pipeline but no trained weapon-detection weights are bundled in this repo
- Automatic police/emergency-service dispatch is explicitly **out of scope** — this is a detection/prioritization tool for human operators, not an automated dispatch system

## Roadmap

- [ ] Wire PostgreSQL persistence behind existing repository interfaces
- [ ] Real-time WebSocket push for live alerts/feed
- [ ] Connect trained model weights to the inference pipeline
- [ ] Remove/replace legacy scaffold stubs in `app/services/` and `app/models/`
- [ ] CI pipeline (lint + test on push)
- [ ] Deployment guide for a real cloud target

---

*Academic / portfolio project. Contributions and feedback welcome via issues.*
