# AI-Based Real-Time Threat Detection and Emergency Response Platform

A production-style academic prototype using YOLO-based computer vision to detect weapons in live video feeds, assess threat levels, and provide security operators with real-time alerts and incident management.

## Current Status: Phase 1 — Development Environment Setup ✅

## Quick Start (Docker)

```bash
# 1. Copy environment file
copy .env.example .env

# 2. Build and start all services
docker-compose up -d

# 3. Verify
#    Backend API:  http://localhost:8000
#    API Docs:     http://localhost:8000/docs
#    Frontend:     http://localhost:3000
#    PostgreSQL:   localhost:5432
#    Redis:        localhost:6379
```

## Quick Start (Local Development)

```powershell
# Run the setup script
.\scripts\setup-local.ps1

# Or manually:

# Terminal 1 - Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm install
npm run dev

# Terminal 3 - Infrastructure
docker-compose up -d postgres redis
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI/Detection | Python, PyTorch, Ultralytics YOLO, OpenCV, ByteTrack |
| Backend | FastAPI, SQLAlchemy, Pydantic, Alembic |
| Database | PostgreSQL 15, Redis 7 |
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Recharts |
| Deployment | Docker, Docker Compose, Nginx |

## Project Structure

```
threat-detection-platform/
├── backend/          # FastAPI application (Python)
├── detection/        # AI/ML detection service (Python + PyTorch)
├── frontend/         # React dashboard (TypeScript)
├── config/           # Infrastructure config (nginx, postgres, redis)
├── scripts/          # Setup and utility scripts
├── docs/             # Documentation
├── docker-compose.yml
└── .env.example
```

## Testing

```bash
# Backend tests
cd backend
.\venv\Scripts\Activate.ps1
pytest tests/ -v
```

## License

Academic project — B.Tech Final Year (Computer Science / Data Science)
