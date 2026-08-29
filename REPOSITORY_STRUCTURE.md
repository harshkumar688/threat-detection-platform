# Repository Structure

## AI-Based Real-Time Threat Detection and Emergency Response Platform

---

## Complete Directory Tree

```
threat-detection-platform/
│
├── docker-compose.yml                  # Multi-container orchestration
├── docker-compose.dev.yml              # Development overrides (hot-reload, debug)
├── .env.example                        # Environment variable template
├── .gitignore                          # Git exclusions
├── README.md                           # Project overview and quickstart
├── Makefile                            # Common commands (build, run, test, migrate)
│
├── docs/                               # Project documentation
│   ├── architecture.md                 # System architecture overview
│   ├── database-design.md             # Database schema documentation
│   ├── api-reference.md               # API endpoint documentation
│   ├── deployment-guide.md            # Deployment instructions
│   ├── user-manual.md                 # End-user guide
│   ├── development-setup.md           # Developer onboarding
│   └── diagrams/                      # Architecture diagrams
│       ├── system-architecture.png
│       ├── data-flow.png
│       └── er-diagram.png
│
├── backend/                            # Python backend (FastAPI)
│   ├── Dockerfile                     # Backend container build
│   ├── Dockerfile.dev                 # Dev container (with hot-reload)
│   ├── requirements.txt              # Production dependencies
│   ├── requirements-dev.txt          # Dev/test dependencies
│   ├── alembic.ini                   # Alembic migration config
│   ├── pytest.ini                    # Pytest configuration
│   ├── .env.example                  # Backend-specific env template
│   │
│   ├── alembic/                       # Database migrations
│   │   ├── env.py                    # Migration environment config
│   │   ├── script.py.mako           # Migration template
│   │   └── versions/                 # Migration version files
│   │       └── .gitkeep
│   │
│   ├── app/                           # Application source code
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app factory + lifespan
│   │   │
│   │   ├── core/                      # Cross-cutting concerns
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # Pydantic Settings (env loading)
│   │   │   ├── security.py          # JWT + password hashing utilities
│   │   │   ├── middleware.py         # CORS, request logging, rate limiting
│   │   │   ├── exceptions.py        # Custom exception classes
│   │   │   ├── exception_handlers.py # Global exception → HTTP response mapping
│   │   │   ├── logging_config.py    # Structured logging (structlog) setup
│   │   │   └── constants.py         # App-wide constants and enums
│   │   │
│   │   ├── api/                       # API layer (routers + dependencies)
│   │   │   ├── __init__.py
│   │   │   ├── deps.py              # Shared dependencies (get_db, get_user, require_role)
│   │   │   └── v1/                   # API version 1
│   │   │       ├── __init__.py
│   │   │       ├── router.py        # Aggregated v1 router
│   │   │       ├── auth.py          # POST /login, /register, /refresh, GET /me
│   │   │       ├── cameras.py       # Camera CRUD + stream control
│   │   │       ├── streams.py       # WebSocket: live video feed
│   │   │       ├── incidents.py     # Incident CRUD + status management
│   │   │       ├── alerts.py        # Alert list + acknowledge + WS live alerts
│   │   │       ├── analytics.py     # Summary, timeline, distribution queries
│   │   │       ├── evidence.py      # Evidence retrieval + file serving
│   │   │       ├── config.py        # System config get/update
│   │   │       ├── audit.py         # Audit log viewing (admin)
│   │   │       └── health.py        # GET /health system status
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   │   ├── __init__.py          # Import all models for Alembic discovery
│   │   │   ├── base.py             # Declarative base + common mixins
│   │   │   ├── user.py             # User + Role models
│   │   │   ├── camera.py           # Camera + CameraLocation models
│   │   │   ├── detection.py        # Detection model
│   │   │   ├── tracked_object.py   # TrackedObject model
│   │   │   ├── incident.py         # Incident + IncidentDetection models
│   │   │   ├── evidence.py         # Evidence model
│   │   │   ├── alert.py            # Alert model
│   │   │   ├── notification.py     # NotificationLog model
│   │   │   ├── audit.py            # AuditLog model
│   │   │   ├── model_version.py    # ModelVersion model
│   │   │   └── config.py           # SystemConfig model
│   │   │
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Base response schemas (success, error, paginated)
│   │   │   ├── auth.py             # Login, register, token schemas
│   │   │   ├── user.py             # User CRUD schemas
│   │   │   ├── camera.py           # Camera CRUD schemas
│   │   │   ├── detection.py        # Detection output schemas
│   │   │   ├── tracked_object.py   # Track schemas
│   │   │   ├── incident.py         # Incident CRUD + status update schemas
│   │   │   ├── evidence.py         # Evidence metadata schemas
│   │   │   ├── alert.py            # Alert schemas
│   │   │   ├── analytics.py        # Analytics response schemas
│   │   │   ├── config.py           # Config schemas
│   │   │   └── audit.py            # Audit log schemas
│   │   │
│   │   ├── services/                  # Business logic layer
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py     # Authentication logic (login, register, token)
│   │   │   ├── user_service.py     # User management logic
│   │   │   ├── camera_service.py   # Camera CRUD + status management
│   │   │   ├── incident_service.py # Incident lifecycle management
│   │   │   ├── alert_service.py    # Alert creation + broadcast
│   │   │   ├── evidence_service.py # Evidence capture + storage + retrieval
│   │   │   ├── analytics_service.py # Data aggregation queries
│   │   │   ├── config_service.py   # System config read/write
│   │   │   ├── audit_service.py    # Audit log writing + querying
│   │   │   └── notification_service.py # Notification delivery tracking
│   │   │
│   │   ├── db/                        # Database session and connection
│   │   │   ├── __init__.py
│   │   │   ├── session.py          # Async session factory + connection pool
│   │   │   └── seed.py             # Initial data seeding (admin user, roles, default config)
│   │   │
│   │   ├── websocket/                 # WebSocket management
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          # Connection registry + broadcast
│   │   │   ├── feed_handler.py     # Live video feed WS logic
│   │   │   └── alert_handler.py    # Real-time alert WS logic
│   │   │
│   │   └── utils/                     # Shared utilities
│   │       ├── __init__.py
│   │       ├── image.py            # Image encoding/decoding (base64, JPEG)
│   │       ├── time_utils.py       # Timezone-aware datetime helpers
│   │       ├── pagination.py       # Pagination parameter parsing
│   │       └── file_utils.py       # Safe file path generation + cleanup
│   │
│   └── tests/                         # Backend test suite
│       ├── __init__.py
│       ├── conftest.py               # Shared fixtures (test DB, client, auth)
│       ├── unit/                      # Unit tests (no DB, no I/O)
│       │   ├── __init__.py
│       │   ├── test_security.py     # JWT + password hashing tests
│       │   ├── test_schemas.py      # Pydantic validation tests
│       │   └── test_utils.py        # Utility function tests
│       ├── integration/               # Integration tests (with DB)
│       │   ├── __init__.py
│       │   ├── test_auth_api.py     # Auth endpoint tests
│       │   ├── test_camera_api.py   # Camera endpoint tests
│       │   ├── test_incident_api.py # Incident endpoint tests
│       │   ├── test_alert_api.py    # Alert endpoint tests
│       │   └── test_analytics_api.py # Analytics endpoint tests
│       └── websocket/                 # WebSocket tests
│           ├── __init__.py
│           └── test_alert_ws.py     # Alert WebSocket tests
│
├── detection/                          # AI/ML detection service
│   ├── Dockerfile                     # Detection container (GPU support)
│   ├── Dockerfile.cpu                 # CPU-only fallback container
│   ├── requirements.txt              # AI/ML dependencies
│   ├── pytest.ini                    # Test config for detection module
│   │
│   ├── src/                           # Detection source code
│   │   ├── __init__.py
│   │   ├── main.py                   # Pipeline entry point + lifecycle
│   │   ├── config.py                 # Detection-specific configuration
│   │   │
│   │   ├── inference/                 # AI model inference
│   │   │   ├── __init__.py
│   │   │   ├── detector.py          # YOLO model loading + inference
│   │   │   ├── preprocessor.py      # Frame preprocessing (resize, normalize)
│   │   │   ├── postprocessor.py     # NMS, confidence filter, bbox scaling
│   │   │   └── model_manager.py     # Model loading, versioning, hot-swap
│   │   │
│   │   ├── tracking/                  # Object tracking
│   │   │   ├── __init__.py
│   │   │   ├── tracker.py           # ByteTrack tracker wrapper
│   │   │   ├── track_state.py       # Track state management + lifecycle
│   │   │   └── association.py       # IoU computation + Hungarian matching
│   │   │
│   │   ├── verification/             # Multi-frame verification
│   │   │   ├── __init__.py
│   │   │   ├── verifier.py          # Sliding window N/M verification logic
│   │   │   └── window.py            # Verification window data structure
│   │   │
│   │   ├── scoring/                   # Threat/risk scoring engine
│   │   │   ├── __init__.py
│   │   │   ├── scorer.py            # Weighted risk score computation
│   │   │   ├── rules.py             # Scoring rules and factor definitions
│   │   │   └── proximity.py         # Person-weapon proximity calculation
│   │   │
│   │   ├── pipeline/                  # Pipeline orchestration
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py          # Main detection pipeline loop
│   │   │   ├── frame_grabber.py     # Camera frame acquisition (threaded)
│   │   │   ├── frame_buffer.py      # Ring buffer for evidence clips
│   │   │   ├── stream_manager.py    # Multi-camera stream coordination
│   │   │   └── decision_engine.py   # Threshold check + incident triggering
│   │   │
│   │   ├── privacy/                   # Privacy-preserving processing
│   │   │   ├── __init__.py
│   │   │   ├── face_detector.py     # Face detection (MediaPipe)
│   │   │   └── anonymizer.py        # Face blurring application
│   │   │
│   │   └── communication/            # Inter-service communication
│   │       ├── __init__.py
│   │       ├── redis_publisher.py   # Publish detections/alerts to Redis
│   │       ├── redis_subscriber.py  # Subscribe to control commands
│   │       └── message_types.py     # Message format definitions
│   │
│   ├── models/                        # AI model weights (gitignored, Docker volume)
│   │   ├── .gitkeep
│   │   └── README.md                # Instructions for downloading/placing weights
│   │
│   └── tests/                         # Detection module tests
│       ├── __init__.py
│       ├── conftest.py               # Shared fixtures (sample frames, mock models)
│       ├── unit/
│       │   ├── __init__.py
│       │   ├── test_preprocessor.py  # Preprocessing tests
│       │   ├── test_postprocessor.py # NMS and filtering tests
│       │   ├── test_tracker.py       # Tracking logic tests
│       │   ├── test_verifier.py      # Multi-frame verification tests
│       │   ├── test_scorer.py        # Risk scoring tests
│       │   ├── test_proximity.py     # Proximity calculation tests
│       │   └── test_anonymizer.py    # Face blur tests
│       ├── integration/
│       │   ├── __init__.py
│       │   ├── test_pipeline.py      # Full pipeline integration test
│       │   └── test_stream_manager.py # Multi-stream test
│       └── fixtures/                  # Test data
│           ├── sample_frames/        # Sample images for testing
│           │   └── .gitkeep
│           └── sample_videos/        # Sample video clips for testing
│               └── .gitkeep
│
├── frontend/                           # React frontend application
│   ├── Dockerfile                     # Production build (Nginx)
│   ├── Dockerfile.dev                 # Dev server (Vite HMR)
│   ├── nginx.conf                    # Nginx config for production serving
│   ├── package.json                  # Node dependencies
│   ├── tsconfig.json                 # TypeScript configuration
│   ├── tsconfig.node.json            # Node-specific TS config
│   ├── vite.config.ts                # Vite build configuration
│   ├── tailwind.config.ts            # TailwindCSS configuration
│   ├── postcss.config.js             # PostCSS configuration
│   ├── .eslintrc.cjs                 # ESLint configuration
│   ├── .prettierrc                   # Prettier formatting rules
│   ├── index.html                    # HTML entry point
│   │
│   ├── public/                        # Static assets (served as-is)
│   │   ├── favicon.ico
│   │   └── logo.svg
│   │
│   └── src/                           # React source code
│       ├── main.tsx                  # App entry point (React root)
│       ├── App.tsx                   # Root component + router
│       ├── routes.tsx                # Route definitions (lazy loaded)
│       ├── vite-env.d.ts             # Vite type declarations
│       │
│       ├── pages/                     # Page-level route components
│       │   ├── LoginPage.tsx
│       │   ├── DashboardPage.tsx
│       │   ├── LiveFeedPage.tsx
│       │   ├── IncidentsPage.tsx
│       │   ├── IncidentDetailPage.tsx
│       │   ├── AnalyticsPage.tsx
│       │   ├── CamerasPage.tsx
│       │   ├── AdminPage.tsx
│       │   └── NotFoundPage.tsx
│       │
│       ├── components/                # Reusable UI components
│       │   ├── common/               # Shared/generic components
│       │   │   ├── Layout.tsx       # App shell (sidebar + header + content)
│       │   │   ├── Sidebar.tsx      # Navigation sidebar
│       │   │   ├── Header.tsx       # Top bar with user menu
│       │   │   ├── ProtectedRoute.tsx # Auth guard wrapper
│       │   │   ├── LoadingSpinner.tsx
│       │   │   ├── ErrorBoundary.tsx
│       │   │   ├── Pagination.tsx
│       │   │   ├── StatusBadge.tsx
│       │   │   ├── SeverityBadge.tsx
│       │   │   └── ConfirmDialog.tsx
│       │   ├── livefeed/             # Live video feed components
│       │   │   ├── VideoPlayer.tsx  # WebSocket video canvas renderer
│       │   │   ├── DetectionOverlay.tsx # Bounding box overlay canvas
│       │   │   ├── FeedGrid.tsx     # Multi-camera grid
│       │   │   └── StreamStatus.tsx # Connection status indicator
│       │   ├── alerts/               # Alert-related components
│       │   │   ├── AlertPanel.tsx   # Real-time alert sidebar
│       │   │   ├── AlertItem.tsx    # Single alert card
│       │   │   ├── AlertBadge.tsx   # Unread count badge
│       │   │   └── AlertSound.tsx   # Audio notification
│       │   ├── incidents/            # Incident management components
│       │   │   ├── IncidentTable.tsx # Filterable table
│       │   │   ├── IncidentCard.tsx # Summary card
│       │   │   ├── IncidentTimeline.tsx # Status history
│       │   │   ├── IncidentStatusForm.tsx # Status update form
│       │   │   └── EvidenceViewer.tsx # Image/video viewer
│       │   ├── analytics/            # Data visualization components
│       │   │   ├── TimelineChart.tsx # Detections over time
│       │   │   ├── SeverityPieChart.tsx # Severity distribution
│       │   │   ├── CameraBarChart.tsx # Per-camera breakdown
│       │   │   ├── StatCard.tsx     # KPI metric card
│       │   │   └── ExportButton.tsx # CSV/PDF export
│       │   └── admin/                # Admin panel components
│       │       ├── UserTable.tsx    # User management table
│       │       ├── UserForm.tsx     # Create/edit user form
│       │       ├── ConfigPanel.tsx  # Detection + scoring config
│       │       ├── CameraForm.tsx   # Add/edit camera form
│       │       └── AuditLogViewer.tsx # Audit log table
│       │
│       ├── hooks/                     # Custom React hooks
│       │   ├── useAuth.ts           # Login/logout/token management
│       │   ├── useWebSocket.ts      # Generic WebSocket hook
│       │   ├── useLiveFeed.ts       # Video stream WebSocket
│       │   ├── useAlerts.ts         # Real-time alert subscription
│       │   ├── useApi.ts            # TanStack Query wrapper
│       │   └── usePermissions.ts    # Role-based UI visibility
│       │
│       ├── services/                  # API client layer
│       │   ├── api.ts               # Axios instance + interceptors
│       │   ├── authService.ts       # /auth/* API calls
│       │   ├── cameraService.ts     # /cameras/* API calls
│       │   ├── incidentService.ts   # /incidents/* API calls
│       │   ├── alertService.ts      # /alerts/* API calls
│       │   ├── analyticsService.ts  # /analytics/* API calls
│       │   ├── configService.ts     # /config/* API calls
│       │   └── evidenceService.ts   # /evidence/* API calls
│       │
│       ├── store/                     # Global state (Zustand)
│       │   ├── authStore.ts         # User, tokens, role state
│       │   ├── alertStore.ts        # Active alerts, unread count
│       │   └── streamStore.ts       # Camera stream connection states
│       │
│       ├── types/                     # TypeScript type definitions
│       │   ├── auth.ts              # Auth-related types
│       │   ├── camera.ts            # Camera types
│       │   ├── detection.ts         # Detection types
│       │   ├── incident.ts          # Incident types
│       │   ├── alert.ts             # Alert types
│       │   ├── analytics.ts         # Analytics response types
│       │   ├── config.ts            # System config types
│       │   └── common.ts            # Shared types (pagination, errors)
│       │
│       ├── utils/                     # Frontend utilities
│       │   ├── constants.ts         # App-wide constants
│       │   ├── formatters.ts        # Date, number, duration formatters
│       │   ├── permissions.ts       # Role permission helpers
│       │   └── validators.ts        # Form validation utilities
│       │
│       └── styles/                    # Global styles
│           └── globals.css          # Tailwind directives + custom CSS
│
├── scripts/                            # Utility scripts
│   ├── setup.sh                      # First-time project setup
│   ├── setup.ps1                     # Windows PowerShell setup
│   ├── seed_db.py                    # Database seeding script
│   ├── download_model.py            # Download YOLO weights
│   ├── generate_test_video.py       # Generate test video with synthetic detections
│   └── evaluate_model.py            # Model evaluation (mAP calculation)
│
└── config/                             # Shared configuration
    ├── nginx/
    │   └── nginx.conf                # Production Nginx config
    ├── postgres/
    │   └── init.sql                  # PostgreSQL initialization (create DB, extensions)
    └── redis/
        └── redis.conf                # Redis configuration
```

---

## Directory Responsibilities

### Root Level

| Directory/File | Responsibility |
|---------------|---------------|
| `docker-compose.yml` | Define all services (backend, detection, frontend, postgres, redis), networks, volumes |
| `docker-compose.dev.yml` | Override for development: hot-reload mounts, debug ports, no build optimization |
| `.env.example` | Template for all environment variables with safe defaults |
| `Makefile` | Shortcut commands: `make build`, `make up`, `make test`, `make migrate`, `make seed` |
| `README.md` | Project overview, quickstart guide, architecture summary |

---

### `docs/` — Project Documentation

| File | Responsibility |
|------|---------------|
| `architecture.md` | High-level system architecture with diagrams |
| `database-design.md` | Complete database schema documentation |
| `api-reference.md` | All API endpoints with request/response examples |
| `deployment-guide.md` | Step-by-step deployment instructions |
| `user-manual.md` | End-user documentation for dashboard operation |
| `development-setup.md` | Developer onboarding: prerequisites, setup steps, workflow |
| `diagrams/` | Visual diagrams (exported from design tools) |

---

### `backend/` — FastAPI Application

| Directory | Responsibility |
|-----------|---------------|
| `app/core/` | Cross-cutting infrastructure: config loading, security primitives, middleware, logging, exception definitions |
| `app/api/` | HTTP layer only: route definitions, request parsing, response formatting. No business logic here |
| `app/api/deps.py` | Dependency injection providers (DB session, authenticated user, role checks) |
| `app/models/` | SQLAlchemy ORM class definitions — one file per entity or closely related group |
| `app/schemas/` | Pydantic models for API input validation and output serialization |
| `app/services/` | Business logic layer: all operations, rules, and workflows. Services are called by routers, never by other routers |
| `app/db/` | Database connection setup, session factory, and data seeding |
| `app/websocket/` | WebSocket connection management, frame broadcasting, alert push |
| `app/utils/` | Pure utility functions with no side effects (image encoding, time conversion, pagination math) |
| `alembic/` | Database migration scripts managed by Alembic |
| `tests/` | Comprehensive test suite (unit + integration + WebSocket) |

---

### `detection/` — AI/ML Detection Service

| Directory | Responsibility |
|-----------|---------------|
| `src/inference/` | Model loading and inference execution. Handles YOLO model lifecycle, preprocessing (resize/normalize), and postprocessing (NMS, confidence filter) |
| `src/tracking/` | Object tracking across frames. Assigns persistent IDs via ByteTrack, manages track state and lifecycle |
| `src/verification/` | Multi-frame detection verification. Implements N-out-of-M sliding window logic to confirm threats |
| `src/scoring/` | Threat risk assessment engine. Computes weighted scores from weapon type, confidence, proximity, duration |
| `src/pipeline/` | Pipeline orchestration: frame grabbing, processing loop coordination, stream management, decision triggering |
| `src/privacy/` | Face detection and anonymization for evidence storage |
| `src/communication/` | Redis pub/sub for inter-service messaging (publish detections, subscribe to commands) |
| `models/` | YOLO weight files (gitignored, mounted as Docker volume). Contains download instructions |
| `tests/` | Detection-specific tests with sample frames and synthetic test data |

---

### `frontend/` — React Dashboard

| Directory | Responsibility |
|-----------|---------------|
| `src/pages/` | Top-level route components. Each page corresponds to a URL path. Pages compose components and call hooks |
| `src/components/common/` | Generic reusable UI: layout shell, navigation, auth guards, loading states, dialogs |
| `src/components/livefeed/` | Video rendering via Canvas + WebSocket. Detection overlay drawing |
| `src/components/alerts/` | Real-time alert panel, individual alert items, audio notifications |
| `src/components/incidents/` | Incident table, detail view, timeline, evidence viewer, status management |
| `src/components/analytics/` | Chart components (Recharts): timelines, pie charts, bar charts, KPI cards |
| `src/components/admin/` | Admin-only: user CRUD, config panel, audit viewer, camera form |
| `src/hooks/` | Custom hooks encapsulating side effects: WebSocket connections, API calls, auth state |
| `src/services/` | API client layer: typed Axios wrappers for each backend endpoint group |
| `src/store/` | Zustand stores for client-side global state (auth, alerts, streams) |
| `src/types/` | TypeScript interface definitions mirroring backend schemas |
| `src/utils/` | Pure helper functions: formatting, validation, permission checks |

---

### `scripts/` — Utility & Setup Scripts

| Script | Responsibility |
|--------|---------------|
| `setup.sh` / `setup.ps1` | One-command project setup: install deps, create .env, pull images |
| `seed_db.py` | Seed database with initial admin user, roles, default config, sample cameras |
| `download_model.py` | Download pre-trained YOLO weights from configured URL |
| `generate_test_video.py` | Create synthetic test video with annotated objects for testing |
| `evaluate_model.py` | Run mAP evaluation on test dataset |

---

### `config/` — Infrastructure Configuration

| Directory | Responsibility |
|-----------|---------------|
| `nginx/` | Nginx reverse proxy config: routing, SSL, static file serving, WebSocket upgrade |
| `postgres/` | PostgreSQL init script: create database, enable extensions (uuid-ossp, pgcrypto) |
| `redis/` | Redis server configuration: memory limits, persistence settings |

---
