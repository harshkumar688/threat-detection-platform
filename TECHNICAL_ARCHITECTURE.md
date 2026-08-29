# Technical Architecture Document

## AI-Based Real-Time Threat Detection and Emergency Response Platform

| Document Info | |
|---|---|
| **Version** | 1.0 |
| **Date** | August 17, 2026 |
| **Status** | Design Complete |
| **References** | SRS_DOCUMENT.md, PROJECT_PLAN.md |

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Component Architecture](#2-component-architecture)
3. [AI Inference Pipeline](#3-ai-inference-pipeline)
4. [Backend Architecture](#4-backend-architecture)
5. [Database Architecture](#5-database-architecture)
6. [Frontend Architecture](#6-frontend-architecture)
7. [API Architecture](#7-api-architecture)
8. [Authentication Architecture](#8-authentication-architecture)
9. [Evidence Storage Architecture](#9-evidence-storage-architecture)
10. [Logging Architecture](#10-logging-architecture)
11. [Error-Handling Architecture](#11-error-handling-architecture)

---

## 1. High-Level Architecture

### 1.1 System Overview

The platform follows a **layered microservice-inspired monolith** architecture deployed as containerized services via Docker Compose. Each logical layer is independently testable but deployed within a single orchestrated environment.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            PRESENTATION LAYER                                 │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │              React + TypeScript SPA (Vite Build)                        │  │
│  │                                                                        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │  │
│  │  │Dashboard │ │Live Feed │ │Incidents │ │Analytics │ │   Admin    │  │  │
│  │  │  Page    │ │  Page    │ │  Page    │ │  Page    │ │   Page     │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│           │ REST (HTTPS)              │ WebSocket (WSS)                       │
└───────────┼───────────────────────────┼──────────────────────────────────────┘
            ▼                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              GATEWAY LAYER                                    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                     Nginx Reverse Proxy                                 │  │
│  │              (SSL termination, static serving, routing)                  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
            │                           │
            ▼                           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            APPLICATION LAYER                                  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │              FastAPI Application (Uvicorn ASGI Server)                   │  │
│  │                                                                        │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │  │
│  │  │  Auth    │ │ Camera   │ │ Incident │ │  Alert   │ │ Analytics  │  │  │
│  │  │ Router   │ │ Router   │ │  Router  │ │  Router  │ │  Router    │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────┘  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────────────────────┐   │  │
│  │  │ Stream   │ │ Config   │ │     WebSocket Manager                │   │  │
│  │  │ Router   │ │ Router   │ │  (live feeds + alert broadcast)      │   │  │
│  │  └──────────┘ └──────────┘ └──────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        Service Layer                                    │  │
│  │                                                                        │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐  │  │
│  │  │ Auth Service │ │Incident Svc  │ │ Alert Svc    │ │Evidence Svc │  │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘  │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐  │  │
│  │  │Camera Svc    │ │Analytics Svc │ │ Audit Svc    │ │ Config Svc  │  │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
            │                                       │
            ▼                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          AI/ML PROCESSING LAYER                               │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │              Detection Pipeline (Async Worker Process)                   │  │
│  │                                                                        │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │  │
│  │  │  Frame   │→ │  YOLO    │→ │  Object  │→ │Multi-Frm │             │  │
│  │  │ Grabber  │  │ Detector │  │ Tracker  │  │ Verifier │             │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │  │
│  │                                                    │                   │  │
│  │  ┌──────────┐  ┌──────────┐                       ▼                   │  │
│  │  │ Privacy  │← │  Threat  │←──────────────────────┘                   │  │
│  │  │ Filter   │  │  Scorer  │                                           │  │
│  │  └──────────┘  └──────────┘                                           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
            │                           │                       │
            ▼                           ▼                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                             DATA LAYER                                        │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   PostgreSQL    │  │     Redis       │  │     File System             │  │
│  │                 │  │                 │  │                             │  │
│  │ • Users         │  │ • Frame queue   │  │ • Evidence snapshots (JPEG) │  │
│  │ • Cameras       │  │ • Alert pub/sub │  │ • Evidence clips (MP4)      │  │
│  │ • Incidents     │  │ • Session cache │  │ • YOLO model weights        │  │
│  │ • Detections    │  │ • Stream state  │  │ • Application logs          │  │
│  │ • Evidence meta │  │ • Rate limiting │  │                             │  │
│  │ • Alerts        │  │                 │  │                             │  │
│  │ • Audit logs    │  │                 │  │                             │  │
│  │ • Config        │  │                 │  │                             │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Communication Patterns

| From | To | Protocol | Pattern | Purpose |
|------|----|----------|---------|---------|
| Frontend | Backend API | HTTP/REST | Request-Response | CRUD operations, data queries |
| Frontend | Backend WS | WebSocket | Bidirectional streaming | Live video frames, real-time alerts |
| Backend | PostgreSQL | TCP (asyncpg) | Connection pool | Persistent data storage |
| Backend | Redis | TCP | Pub/Sub + Cache | Alert broadcast, frame queue, caching |
| Detection Worker | Redis | TCP | Publish | Push detections/alerts to backend |
| Backend | File System | Local I/O | Direct write/read | Evidence storage |
| Detection Worker | GPU/CPU | CUDA/CPU | Direct | Model inference |

### 1.3 Deployment Topology

```
Docker Compose Network (bridge: threat-net)
├── frontend-container     (Port 80 → Nginx → React static)
├── backend-container      (Port 8000 → Uvicorn → FastAPI)
├── detection-container    (Internal → AI pipeline worker)
├── postgres-container     (Port 5432 → PostgreSQL)
└── redis-container        (Port 6379 → Redis)
```

| Container | Base Image | Resources | Volumes |
|-----------|-----------|-----------|---------|
| frontend | node:20-alpine → nginx:alpine | 256MB RAM | - |
| backend | python:3.11-slim | 1GB RAM | ./evidence:/app/evidence |
| detection | nvidia/cuda:12.1-runtime OR python:3.11-slim | 2-4GB RAM + GPU | ./models:/app/models |
| postgres | postgres:15-alpine | 512MB RAM | pgdata:/var/lib/postgresql/data |
| redis | redis:7-alpine | 256MB RAM | - |

---

## 2. Component Architecture

### 2.1 Component Interaction Diagram

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Camera    │ RTSP/   │   Frame     │ frames  │    YOLO     │
│   Source    │ USB ──→ │   Grabber   │ ──────→ │  Detector   │
└─────────────┘         └─────────────┘         └──────┬──────┘
                                                       │ detections
                                                       ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Threat    │ verified│ Multi-Frame │ tracked │   Object    │
│   Scorer    │ ←────── │  Verifier   │ ←────── │  Tracker    │
└──────┬──────┘         └─────────────┘         └─────────────┘
       │ scored threats
       ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Decision   │ create  │  Incident   │ notify  │   Alert     │
│  Engine     │ ──────→ │  Service    │ ──────→ │  Service    │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │                       ▼                       ▼
       │                ┌─────────────┐         ┌─────────────┐
       │                │  Evidence   │         │  WebSocket  │
       │                │  Service    │         │  Manager    │
       │                └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       ▼                       ▼                       ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Audit      │         │ File System │         │  Dashboard  │
│  Service    │         │ (Evidence)  │         │  Clients    │
└──────┬──────┘         └─────────────┘         └─────────────┘
       │
       ▼
┌─────────────┐
│ PostgreSQL  │
└─────────────┘
```

### 2.2 Component Catalog

Each component is described with its full specification below.

---

#### COMP-01: Frame Grabber

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Continuously read video frames from camera sources (USB, RTSP, file) at a configurable FPS and deliver them to the detection pipeline |
| **Inputs** | Camera stream URL (RTSP/HTTP/device index), target FPS (int), resolution (tuple) |
| **Outputs** | Raw BGR frames (numpy ndarray, shape: H×W×3), frame metadata (timestamp, frame_number, camera_id) |
| **Dependencies** | OpenCV (cv2.VideoCapture), camera hardware/network |
| **Failure Cases** | 1) Camera unreachable → log error, enter reconnection loop with exponential backoff (1s, 2s, 4s, max 30s). 2) Frame decode error → skip frame, increment error counter. 3) FPS below threshold → emit stream health warning via Redis |
| **Threading Model** | One thread per camera stream; frames pushed to a thread-safe queue (maxsize=30) |
| **Configuration** | `target_fps`, `resolution`, `reconnect_max_retries`, `reconnect_backoff_base` |

---

#### COMP-02: YOLO Detector

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Run YOLOv8/v9 inference on input frames to detect weapons and persons |
| **Inputs** | Raw frame (numpy ndarray), confidence_threshold (float), nms_iou_threshold (float) |
| **Outputs** | List of detections: `[{class_id, class_name, confidence, bbox: [x1,y1,x2,y2]}]` |
| **Dependencies** | Ultralytics library, PyTorch, CUDA (optional), model weights file (.pt) |
| **Failure Cases** | 1) Model file missing → raise startup error, prevent pipeline start. 2) CUDA OOM → fallback to CPU mode, log warning. 3) Inference timeout (>500ms) → skip frame, log performance warning. 4) Corrupted frame → skip with error log |
| **Performance** | GPU: ~20-40ms/frame (640×640), CPU: ~150-200ms/frame |
| **Configuration** | `model_path`, `confidence_threshold`, `nms_iou_threshold`, `input_size`, `device` (cuda/cpu/auto) |

---

#### COMP-03: Object Tracker

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Assign persistent unique IDs to detected objects across consecutive frames, maintaining identity through brief occlusions |
| **Inputs** | Current frame detections `[{class_name, confidence, bbox}]`, previous track states |
| **Outputs** | Tracked objects `[{track_id, class_name, confidence, bbox, age_frames, age_seconds}]` |
| **Dependencies** | ByteTrack algorithm implementation, NumPy |
| **Failure Cases** | 1) No detections in frame → all active tracks age by 1, no new assignments. 2) Track lost for > max_age frames → track deleted. 3) ID counter overflow → reset with new offset (astronomically unlikely in practice) |
| **State** | Maintains internal track state dict: `{track_id: {bbox_history, class, last_seen_frame, age}}` |
| **Configuration** | `max_age` (frames before track deletion, default: 30), `min_hits` (minimum detections to confirm track, default: 3), `iou_threshold` (for association, default: 0.3) |

---

#### COMP-04: Multi-Frame Verifier

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Confirm weapon detections by requiring consistent appearance across multiple frames (N out of M), eliminating single-frame false positives |
| **Inputs** | Tracked objects with weapon class from current frame, sliding window history per track_id |
| **Outputs** | Verified threats `[{track_id, class_name, avg_confidence, frame_count, first_seen, last_seen}]` |
| **Dependencies** | Object Tracker output, collections.deque for sliding window |
| **Failure Cases** | 1) Track appears in < N frames within M window → not verified, no output. 2) Track oscillates between weapon/non-weapon class → treat as unverified. 3) Sliding window memory exhaustion (extreme edge case) → cap at 1000 active windows |
| **Algorithm** | For each weapon track_id, maintain a deque of size M. On each frame, append 1 (detected) or 0 (not detected). If sum(window) >= N → verified |
| **Configuration** | `N` (required detections, default: 3), `M` (window size, default: 5) |

---

#### COMP-05: Threat Scorer

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Compute a numerical risk score (0.0–1.0) for each verified threat using configurable weighted factors, and map to severity level |
| **Inputs** | Verified threat object, all current person detections (for proximity calc), scoring weights config |
| **Outputs** | Scored threat `{track_id, class_name, risk_score, severity, scoring_breakdown}` |
| **Dependencies** | NumPy (distance calculations), SystemConfig (weights from DB) |
| **Failure Cases** | 1) No persons detected → proximity_score defaults to 0.5 (neutral). 2) Invalid weights (sum=0) → use default weights, log config error. 3) Score out of range → clamp to [0.0, 1.0] |
| **Algorithm** | `risk_score = clamp(w1*weapon_type + w2*avg_confidence + w3*proximity + w4*duration + w5*weapon_count, 0.0, 1.0)` |
| **Severity Mapping** | 0.0–0.3: Low, 0.3–0.5: Medium, 0.5–0.7: High, 0.7–1.0: Critical |
| **Configuration** | `weights: {w1, w2, w3, w4, w5}`, `weapon_type_scores: {handgun: 0.9, rifle: 1.0, knife: 0.6}`, `severity_thresholds` |

---

#### COMP-06: Decision Engine

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Evaluate scored threats against the incident creation threshold and trigger downstream actions (incident creation, evidence capture, alert generation) |
| **Inputs** | Scored threats from Threat Scorer, incident_threshold config |
| **Outputs** | Commands: CreateIncident, CaptureEvidence, GenerateAlert (published to Redis) |
| **Dependencies** | Redis (pub/sub for command dispatch), Threat Scorer output |
| **Failure Cases** | 1) Redis unavailable → buffer commands in memory (max 100), retry. 2) Duplicate incident for same track → check if active incident exists for track_id, skip if so. 3) Threshold set too low → excessive incidents (mitigated by configurable threshold) |
| **Deduplication** | Maintains a set of active track_ids with open incidents; only creates new incident if track_id has no active incident |
| **Configuration** | `incident_threshold` (default: 0.5), `cooldown_seconds` (minimum time between incidents for same camera, default: 30) |

---

#### COMP-07: Privacy Filter

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Detect and blur faces in evidence frames/clips before storage to preserve privacy |
| **Inputs** | Raw frame (numpy ndarray), anonymization_enabled flag |
| **Outputs** | Anonymized frame with faces blurred (Gaussian, σ≥15) |
| **Dependencies** | MediaPipe Face Detection OR Ultralytics YOLO-face, OpenCV (GaussianBlur) |
| **Failure Cases** | 1) Face detection model fails → log warning, store frame without anonymization, flag evidence as "unprocessed". 2) No faces detected → return frame unchanged. 3) Anonymization disabled via config → pass-through |
| **Performance** | ~10-20ms per frame (MediaPipe), acceptable overhead for evidence (not real-time) |
| **Configuration** | `enabled` (bool), `blur_sigma` (int, default: 23), `detection_confidence` (float, default: 0.5) |

---

#### COMP-08: WebSocket Manager

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Manage WebSocket connections for live video streaming and real-time alert delivery to dashboard clients |
| **Inputs** | Annotated frames from detection pipeline (via Redis), alert events, client connections |
| **Outputs** | Base64-encoded JPEG frames to subscribed clients, JSON alert messages to all authenticated clients |
| **Dependencies** | FastAPI WebSocket, Redis (subscribe to frame/alert channels), JWT validation |
| **Failure Cases** | 1) Client disconnects → remove from connection pool, clean up subscription. 2) Slow client (back-pressure) → drop frames for that client, maintain latest-only. 3) Redis connection lost → reconnect with backoff, pause streaming temporarily. 4) Too many connections (>100) → reject new connections with 503 |
| **Channels** | `stream:{camera_id}` (video frames), `alerts:broadcast` (alert notifications) |
| **Frame Throttle** | Max 15 fps to clients; server-side frame skipping if pipeline produces faster |

---

#### COMP-09: Incident Service

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Create, update, and query incident records; manage incident lifecycle; coordinate evidence capture |
| **Inputs** | CreateIncident command (from Decision Engine), status update requests (from API), query filters |
| **Outputs** | Incident records (to DB), evidence capture trigger, alert generation trigger |
| **Dependencies** | PostgreSQL (SQLAlchemy), Evidence Service, Alert Service, Audit Service |
| **Failure Cases** | 1) DB write failure → retry once, then return error to caller with incident data for manual retry. 2) Evidence capture fails → incident still created, evidence marked as "failed". 3) Concurrent status update → use optimistic locking (version column) |
| **Lifecycle** | Open → Acknowledged → Resolved → Closed (reverse transitions not allowed) |

---

#### COMP-10: Alert Service

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Generate alert records, broadcast real-time notifications to connected clients, manage alert acknowledgement |
| **Inputs** | Incident creation event, alert acknowledgement requests |
| **Outputs** | Alert records (to DB), WebSocket broadcast messages (via Redis pub/sub) |
| **Dependencies** | PostgreSQL, Redis (pub/sub), WebSocket Manager |
| **Failure Cases** | 1) WebSocket broadcast fails → alert still persisted in DB (clients will see it on reload). 2) Redis pub/sub down → fallback to direct WebSocket push from service. 3) DB write failure → log error, still attempt broadcast (alert is transient) |

---

#### COMP-11: Evidence Service

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Capture, store, and manage evidence files (snapshots and video clips); apply privacy filtering; enforce retention policies |
| **Inputs** | Capture command (frame buffer, camera_id, incident_id), retrieval requests |
| **Outputs** | Evidence files (JPEG/MP4) on disk, evidence metadata records in DB |
| **Dependencies** | OpenCV (image/video writing), Privacy Filter, PostgreSQL, File System |
| **Failure Cases** | 1) Disk full → log critical error, skip evidence capture, mark incident as "evidence_failed". 2) Frame buffer insufficient for clip duration → capture shorter clip, record actual duration. 3) Privacy filter fails → store with flag "anonymization_pending" |

---

#### COMP-12: Analytics Service

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Aggregate and query historical detection/incident data for dashboard charts and reports |
| **Inputs** | Query parameters (time range, camera filter, severity filter, granularity) |
| **Outputs** | Aggregated data: time series, distributions, summaries |
| **Dependencies** | PostgreSQL (aggregate queries), Redis (optional result caching) |
| **Failure Cases** | 1) Large query timeout → limit time range, return partial results with warning. 2) Cache miss → compute from DB (slower but correct) |
| **Caching** | Cache aggregated results in Redis with 5-minute TTL for frequently accessed dashboards |

---

## 3. AI Inference Pipeline

### 3.1 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DETECTION PIPELINE (per camera)                        │
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │   Thread:   │    │   Thread:   │    │   Thread:   │                │
│  │ FrameGrab   │    │ FrameGrab   │    │ FrameGrab   │   ... (N cams) │
│  │  Camera 1   │    │  Camera 2   │    │  Camera 3   │                │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                │
│         │                  │                  │                         │
│         └──────────────────┼──────────────────┘                         │
│                            ▼                                            │
│                   ┌─────────────────┐                                   │
│                   │  Frame Queue    │  (thread-safe, per-camera)         │
│                   │  maxsize=30     │                                   │
│                   └────────┬────────┘                                   │
│                            │                                            │
│                            ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Inference Loop (Main Processing Thread)              │   │
│  │                                                                  │   │
│  │  for each camera queue:                                          │   │
│  │    1. Dequeue latest frame (skip stale frames)                   │   │
│  │    2. Preprocess (resize to 640×640, normalize)                  │   │
│  │    3. Batch inference if multiple frames ready                   │   │
│  │    4. Post-process (NMS, confidence filter)                      │   │
│  │    5. Update tracker state                                       │   │
│  │    6. Check verification windows                                 │   │
│  │    7. Score verified threats                                     │   │
│  │    8. Publish annotated frame to Redis (for WebSocket)           │   │
│  │    9. If threshold exceeded → publish incident command            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Frame Buffer (Ring Buffer per Camera)                │   │
│  │                                                                  │   │
│  │  Stores last 300 frames (10s × 30fps) for evidence clip capture  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Pipeline Stages Detail

#### Stage 1: Frame Acquisition

| Attribute | Details |
|-----------|---------|
| **Process** | OpenCV VideoCapture reads frames in a dedicated thread per camera |
| **Output Format** | numpy ndarray (BGR, uint8), shape: (H, W, 3) |
| **Frame Skipping** | If queue is full, newest frame replaces oldest (only latest matters) |
| **Timing** | Target interval = 1000/target_fps ms between reads |
| **Metadata Attached** | `{camera_id, timestamp_utc, frame_number, original_resolution}` |

#### Stage 2: Preprocessing

| Attribute | Details |
|-----------|---------|
| **Resize** | Letterbox resize to model input size (640×640) maintaining aspect ratio |
| **Normalization** | Pixel values scaled to [0, 1] float32 |
| **Color Space** | BGR → RGB conversion (YOLO expects RGB) |
| **Batching** | Up to 4 frames batched for single inference call if multiple cameras ready simultaneously |
| **Output** | Tensor: shape (batch, 3, 640, 640), dtype float32 |

#### Stage 3: Inference

| Attribute | Details |
|-----------|---------|
| **Model** | Ultralytics YOLO (model.predict()) |
| **Device Selection** | Auto-detect GPU availability; fallback to CPU |
| **Output Raw** | Tensor of shape (batch, num_detections, 6) → [x1, y1, x2, y2, confidence, class_id] |
| **Classes** | 0: handgun, 1: rifle, 2: knife, 3: person |
| **Half Precision** | FP16 on GPU for speed (model.predict(half=True)) |

#### Stage 4: Post-Processing

| Attribute | Details |
|-----------|---------|
| **Confidence Filter** | Remove detections below threshold (default 0.5) |
| **NMS** | IoU threshold 0.45; per-class NMS |
| **Bbox Scaling** | Scale coordinates back to original frame resolution |
| **Output** | List[Detection] per frame: `{class_name, confidence, bbox, camera_id, timestamp}` |

#### Stage 5: Tracking

| Attribute | Details |
|-----------|---------|
| **Algorithm** | ByteTrack (preferred) — handles low-confidence detections as "second association" |
| **Input** | Current frame detections + previous frame track states |
| **Association** | IoU-based matching with Hungarian algorithm |
| **Output** | TrackedObject list with persistent track_id |
| **State Management** | Per-camera tracker instance; tracks maintained independently |

#### Stage 6: Verification

| Attribute | Details |
|-----------|---------|
| **Sliding Window** | Per track_id, maintain deque of size M |
| **Logic** | If weapon track has ≥ N hits in M-frame window → verified |
| **Output** | VerifiedThreat with avg_confidence across positive frames |
| **Reset** | Window resets when track is deleted (lost for max_age frames) |

#### Stage 7: Scoring & Decision

| Attribute | Details |
|-----------|---------|
| **Scoring** | Compute weighted risk_score per verified threat |
| **Proximity** | Euclidean distance between weapon bbox center and nearest person bbox center, normalized by frame diagonal |
| **Duration** | `min(track_age_seconds / 10.0, 1.0)` — caps at 10s |
| **Threshold Check** | If risk_score > incident_threshold AND no active incident for this track → create incident |

### 3.3 Performance Budget (per frame, single camera)

| Stage | GPU (ms) | CPU (ms) |
|-------|----------|----------|
| Frame read | 2 | 2 |
| Preprocess | 3 | 5 |
| Inference | 25 | 150 |
| Post-process | 2 | 3 |
| Tracking | 3 | 5 |
| Verification | <1 | <1 |
| Scoring | <1 | <1 |
| Frame annotation | 3 | 5 |
| Redis publish | 2 | 2 |
| **Total** | **~41ms (24 FPS)** | **~173ms (5.7 FPS)** |

---

## 4. Backend Architecture

### 4.1 Application Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app factory, lifespan events
│   ├── core/
│   │   ├── config.py           # Pydantic Settings (env-based)
│   │   ├── security.py         # JWT creation/validation, password hashing
│   │   ├── middleware.py       # CORS, request logging, rate limiting
│   │   ├── logging_config.py   # Structured logging setup
│   │   └── exceptions.py       # Custom exception classes + handlers
│   ├── api/
│   │   ├── deps.py             # Dependency injection (get_db, get_current_user)
│   │   └── v1/
│   │       ├── router.py       # Aggregate v1 router
│   │       ├── auth.py         # Auth endpoints
│   │       ├── cameras.py      # Camera CRUD + stream control
│   │       ├── streams.py      # WebSocket endpoints for live feed
│   │       ├── incidents.py    # Incident CRUD
│   │       ├── alerts.py       # Alert endpoints + WebSocket
│   │       ├── analytics.py    # Analytics query endpoints
│   │       ├── config.py       # System config endpoints
│   │       └── audit.py        # Audit log endpoints
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic
│   ├── detection/              # AI pipeline (separate process)
│   ├── db/
│   │   ├── session.py          # Async session factory
│   │   └── base.py             # Declarative base, model imports
│   └── utils/
│       ├── image.py            # Image encoding/decoding helpers
│       └── time_utils.py       # Timezone-aware datetime helpers
├── alembic/                    # DB migrations
├── tests/                      # Test suite
├── Dockerfile
└── requirements.txt
```

### 4.2 Request Lifecycle

```
Client Request
      │
      ▼
┌─────────────────┐
│ Nginx (proxy)   │  → SSL termination, static files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Uvicorn (ASGI)  │  → HTTP/WS protocol handling
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Middleware Stack │
│ 1. CORS         │  → Origin validation
│ 2. Request Log  │  → Log method, path, duration
│ 3. Rate Limit   │  → Check Redis counter
│ 4. Error Handler│  → Catch unhandled exceptions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Router Dispatch  │  → Match path to handler
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Dependency       │
│ Injection        │
│ • get_db_session │  → AsyncSession from pool
│ • get_current_user│ → JWT decode + user lookup
│ • require_role   │  → RBAC check
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Route Handler    │  → Validate input (Pydantic)
│                  │  → Call service method
│                  │  → Return response schema
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Service Layer    │  → Business logic
│                  │  → DB operations
│                  │  → Cross-service calls
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Response         │  → Serialize to JSON
│ (Pydantic model) │  → Set status code
└─────────────────┘
```

### 4.3 Dependency Injection Pattern

| Dependency | Provider | Scope | Purpose |
|-----------|----------|-------|---------|
| `get_db` | AsyncGenerator | Per-request | SQLAlchemy async session |
| `get_current_user` | Depends(get_db) + JWT | Per-request | Authenticated user model |
| `require_admin` | Depends(get_current_user) | Per-request | Admin role enforcement |
| `require_operator` | Depends(get_current_user) | Per-request | Operator+ role enforcement |
| `get_redis` | Connection pool | Singleton | Redis client |
| `get_settings` | Cached | Singleton | App configuration |

### 4.4 Background Tasks

| Task | Trigger | Purpose |
|------|---------|---------|
| Evidence Cleanup | Scheduled (daily) | Delete evidence files older than retention period |
| Stream Health Check | Scheduled (30s) | Verify camera connections, update status |
| Audit Log Rotation | Scheduled (weekly) | Archive old audit entries (optional) |
| Model Reload | On config change | Hot-reload YOLO weights without restart |

---

## 5. Database Architecture

### 5.1 Entity-Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    users     │       │     cameras      │       │   detections     │
├──────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)      │       │ id (PK)          │       │ id (PK)          │
│ email        │       │ name             │  1──M │ camera_id (FK)   │
│ password_hash│       │ location         │◄──────│ timestamp        │
│ role         │       │ stream_url       │       │ class_label      │
│ is_active    │       │ status           │       │ confidence       │
│ created_at   │       │ metadata_json    │       │ bbox_json        │
│ updated_at   │       │ created_at       │       │ track_id         │
└──────┬───────┘       │ updated_at       │       │ frame_number     │
       │               └────────┬─────────┘       │ is_verified      │
       │                        │                 └────────┬─────────┘
       │                        │ 1──M                     │
       │                        ▼                          │
       │               ┌──────────────────┐                │
       │               │    incidents     │                │
       │               ├──────────────────┤                │
       │               │ id (PK)          │                │
       │               │ camera_id (FK)   │      ┌─────────┴────────┐
       │               │ severity         │      │incident_detections│
       │               │ status           │      ├──────────────────┤
       │               │ risk_score       │      │ id (PK)          │
       │               │ description      │◄─────│ incident_id (FK) │
       │               │ started_at       │  1──M│ detection_id (FK)│
       │               │ acknowledged_at  │      └──────────────────┘
       │               │ resolved_at      │
       │               │ closed_at        │
       │               │ version          │  (optimistic locking)
       │               │ created_at       │
       │               └───────┬──────────┘
       │                       │
       │            ┌──────────┼──────────┐
       │            │ 1──M     │ 1──M     │
       │            ▼          ▼          │
       │   ┌──────────────┐  ┌──────────────────┐
       │   │   evidence   │  │     alerts       │
       │   ├──────────────┤  ├──────────────────┤
       │   │ id (PK)      │  │ id (PK)          │
       │   │ incident_id  │  │ incident_id (FK) │
       │   │ type         │  │ severity         │
       │   │ file_path    │  │ message          │
       │   │ file_size    │  │ is_acknowledged  │
       │   │ duration_sec │  │ acknowledged_by  │◄── users.id
       │   │ anonymized   │  │ acknowledged_at  │
       │   │ captured_at  │  │ created_at       │
       │   │ metadata_json│  └──────────────────┘
       │   └──────────────┘
       │
       │   ┌──────────────────┐    ┌──────────────────┐
       │   │   audit_logs     │    │  system_config   │
       │   ├──────────────────┤    ├──────────────────┤
       └──►│ id (PK)          │    │ id (PK)          │
       1──M│ user_id (FK)     │    │ key (unique)     │
           │ action           │    │ value_json       │
           │ resource_type    │    │ updated_by (FK)  │
           │ resource_id      │    │ updated_at       │
           │ details_json     │    └──────────────────┘
           │ ip_address       │
           │ timestamp        │
           └──────────────────┘
```

### 5.2 Table Specifications

#### users
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default gen_random_uuid() | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Indexed |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt hash |
| role | VARCHAR(20) | NOT NULL, CHECK (admin/operator/viewer) | |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Soft delete |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Auto-updated |

#### cameras
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| name | VARCHAR(100) | NOT NULL | Display name |
| location | VARCHAR(255) | | Physical location |
| stream_url | VARCHAR(500) | NOT NULL | RTSP/HTTP/device |
| status | VARCHAR(20) | DEFAULT 'offline' | online/offline/processing/error |
| metadata_json | JSONB | | Flexible metadata |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

#### detections
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGSERIAL | PK | High-volume table |
| camera_id | UUID | FK → cameras.id, NOT NULL | Indexed |
| timestamp | TIMESTAMPTZ | NOT NULL | Indexed (for time queries) |
| class_label | VARCHAR(20) | NOT NULL | handgun/rifle/knife/person |
| confidence | FLOAT | NOT NULL, CHECK (0-1) | |
| bbox_json | JSONB | NOT NULL | {x1, y1, x2, y2} |
| track_id | INTEGER | | From tracker |
| frame_number | BIGINT | | |
| is_verified | BOOLEAN | DEFAULT false | Multi-frame verified |

**Index**: `idx_detections_camera_time` on (camera_id, timestamp DESC)
**Partitioning**: Consider monthly range partitioning on timestamp for large deployments

#### incidents
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| camera_id | UUID | FK → cameras.id, NOT NULL | |
| severity | VARCHAR(10) | NOT NULL | low/medium/high/critical |
| status | VARCHAR(15) | NOT NULL, DEFAULT 'open' | open/acknowledged/resolved/closed |
| risk_score | FLOAT | NOT NULL | 0.0–1.0 |
| description | TEXT | | Auto-generated or manual |
| started_at | TIMESTAMPTZ | NOT NULL | First detection time |
| acknowledged_at | TIMESTAMPTZ | | |
| resolved_at | TIMESTAMPTZ | | |
| closed_at | TIMESTAMPTZ | | |
| version | INTEGER | NOT NULL, DEFAULT 1 | Optimistic locking |
| created_at | TIMESTAMPTZ | NOT NULL | |

**Index**: `idx_incidents_status` on (status), `idx_incidents_camera` on (camera_id)

#### evidence
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| incident_id | UUID | FK → incidents.id, NOT NULL | |
| type | VARCHAR(10) | NOT NULL | snapshot/clip |
| file_path | VARCHAR(500) | NOT NULL | Relative path |
| file_size | BIGINT | | Bytes |
| duration_sec | FLOAT | | For clips only |
| anonymized | BOOLEAN | DEFAULT false | |
| captured_at | TIMESTAMPTZ | NOT NULL | |
| metadata_json | JSONB | | Resolution, codec, etc. |

#### alerts
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| incident_id | UUID | FK → incidents.id, NOT NULL | |
| severity | VARCHAR(10) | NOT NULL | Matches incident severity |
| message | TEXT | NOT NULL | Human-readable description |
| is_acknowledged | BOOLEAN | DEFAULT false | |
| acknowledged_by | UUID | FK → users.id, NULLABLE | |
| acknowledged_at | TIMESTAMPTZ | | |
| created_at | TIMESTAMPTZ | NOT NULL | Indexed |

#### audit_logs
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | BIGSERIAL | PK | Append-only |
| user_id | UUID | FK → users.id, NULLABLE | NULL for system actions |
| action | VARCHAR(50) | NOT NULL | login, create_incident, etc. |
| resource_type | VARCHAR(50) | | incident, camera, user, config |
| resource_id | VARCHAR(100) | | |
| details_json | JSONB | | Action-specific details |
| ip_address | VARCHAR(45) | | IPv4/IPv6 |
| timestamp | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Indexed |

**Index**: `idx_audit_timestamp` on (timestamp DESC), `idx_audit_user` on (user_id)

#### system_config
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK | |
| key | VARCHAR(100) | UNIQUE, NOT NULL | detection.confidence_threshold |
| value_json | JSONB | NOT NULL | Flexible value storage |
| updated_by | UUID | FK → users.id | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

### 5.3 Migration Strategy

| Aspect | Approach |
|--------|----------|
| Tool | Alembic with async support |
| Naming | `YYYYMMDD_HHMMSS_description.py` |
| Environments | Development (auto-migrate on startup), Production (manual migration) |
| Rollback | Each migration includes downgrade function |
| Seed Data | Initial admin user + default config seeded via migration |

---

## 6. Frontend Architecture

### 6.1 Application Structure

```
frontend/src/
├── main.tsx                    # App entry point
├── App.tsx                     # Root component, router setup
├── routes.tsx                  # Route definitions with lazy loading
│
├── pages/                     # Page-level components (one per route)
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx
│   ├── LiveFeedPage.tsx
│   ├── IncidentsPage.tsx
│   ├── IncidentDetailPage.tsx
│   ├── AnalyticsPage.tsx
│   ├── CamerasPage.tsx
│   └── AdminPage.tsx
│
├── components/                # Reusable UI components
│   ├── common/
│   │   ├── Layout.tsx         # App shell (sidebar, header, content)
│   │   ├── ProtectedRoute.tsx # Auth guard
│   │   ├── LoadingSpinner.tsx
│   │   ├── ErrorBoundary.tsx
│   │   └── Pagination.tsx
│   ├── livefeed/
│   │   ├── VideoPlayer.tsx    # WebSocket video renderer
│   │   ├── DetectionOverlay.tsx # Canvas overlay for bboxes
│   │   └── FeedGrid.tsx       # Multi-camera grid layout
│   ├── alerts/
│   │   ├── AlertPanel.tsx     # Real-time alert sidebar
│   │   ├── AlertItem.tsx      # Single alert card
│   │   └── AlertBadge.tsx     # Unread count indicator
│   ├── incidents/
│   │   ├── IncidentTable.tsx  # Filterable incident list
│   │   ├── IncidentCard.tsx   # Summary card
│   │   ├── IncidentTimeline.tsx # Status timeline
│   │   └── EvidenceViewer.tsx # Image/video evidence display
│   ├── analytics/
│   │   ├── TimelineChart.tsx  # Detection over time (Recharts)
│   │   ├── SeverityPieChart.tsx
│   │   ├── CameraHeatmap.tsx
│   │   └── StatCard.tsx       # KPI summary card
│   └── admin/
│       ├── UserTable.tsx
│       ├── UserForm.tsx
│       ├── ConfigPanel.tsx
│       └── AuditLogViewer.tsx
│
├── hooks/                     # Custom React hooks
│   ├── useAuth.ts             # Auth state + login/logout
│   ├── useWebSocket.ts        # WebSocket connection management
│   ├── useLiveFeed.ts         # Video frame WebSocket
│   ├── useAlerts.ts           # Real-time alert subscription
│   └── useApi.ts              # Base API hook (TanStack Query wrapper)
│
├── services/                  # API client layer
│   ├── api.ts                 # Axios instance with interceptors
│   ├── authService.ts         # Auth API calls
│   ├── cameraService.ts       # Camera API calls
│   ├── incidentService.ts     # Incident API calls
│   ├── alertService.ts        # Alert API calls
│   ├── analyticsService.ts    # Analytics API calls
│   └── configService.ts       # Config API calls
│
├── store/                     # Global state (Zustand)
│   ├── authStore.ts           # User, tokens, role
│   ├── alertStore.ts          # Active alerts, unread count
│   └── streamStore.ts         # Active stream states
│
├── types/                     # TypeScript interfaces
│   ├── auth.ts
│   ├── camera.ts
│   ├── detection.ts
│   ├── incident.ts
│   ├── alert.ts
│   └── analytics.ts
│
└── utils/
    ├── constants.ts           # App-wide constants
    ├── formatters.ts          # Date, number formatters
    └── permissions.ts         # Role permission helpers
```

### 6.2 State Management Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      STATE LAYERS                                  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Server State (TanStack Query)                               │  │
│  │ • Incidents list (paginated, cached)                        │  │
│  │ • Camera list                                               │  │
│  │ • Analytics data                                            │  │
│  │ • Audit logs                                                │  │
│  │                                                             │  │
│  │ Features: auto-refetch, cache invalidation, optimistic      │  │
│  │ updates, background polling                                 │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Client State (Zustand)                                      │  │
│  │ • Auth state (user, token, role)                            │  │
│  │ • Active alerts (from WebSocket)                            │  │
│  │ • Stream connection states                                  │  │
│  │ • UI preferences (grid layout, theme)                       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Real-Time State (WebSocket)                                 │  │
│  │ • Live video frames (not stored, rendered immediately)      │  │
│  │ • Alert notifications (pushed to Zustand store)             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.3 Component Communication

| Pattern | Use Case | Example |
|---------|----------|---------|
| Props down | Parent → Child data passing | IncidentTable → IncidentCard |
| Callbacks up | Child → Parent events | AlertItem → AlertPanel (onAcknowledge) |
| Zustand store | Cross-component shared state | Auth token accessed by API layer |
| TanStack Query | Server data with caching | Incident list with auto-refetch |
| WebSocket hook | Real-time streaming data | useLiveFeed provides frames to VideoPlayer |
| Context (React) | Theme, layout preferences | Avoided for performance-critical paths |

### 6.4 Video Rendering Strategy

| Attribute | Details |
|-----------|---------|
| **Transport** | WebSocket binary frames (JPEG encoded) |
| **Rendering** | HTML5 Canvas element (not <video> tag) |
| **Overlay** | Separate Canvas layer for detection bounding boxes |
| **Frame Rate** | Client displays at received rate (max 15fps from server) |
| **Backpressure** | If client can't keep up, only latest frame is rendered (skip stale) |
| **Memory** | No frame buffering on client; immediate render and discard |
| **Fallback** | If WebSocket disconnects, show "Stream Offline" placeholder |

---

## 7. API Architecture

### 7.1 API Design Principles

| Principle | Implementation |
|-----------|---------------|
| RESTful | Resource-based URLs, proper HTTP verbs |
| Versioned | `/api/v1/` prefix for all endpoints |
| Paginated | All list endpoints support `?page=1&page_size=20` |
| Filterable | Query parameters for filtering (e.g., `?severity=high&status=open`) |
| Consistent Errors | Uniform error response format across all endpoints |
| Documented | Auto-generated OpenAPI (Swagger) via FastAPI |
| Authenticated | Bearer token required (except /health, /auth/login) |

### 7.2 URL Structure

```
/api/v1/
├── auth/
│   ├── POST   /login          → Authenticate
│   ├── POST   /register       → Create account
│   ├── POST   /refresh        → Refresh token
│   └── GET    /me             → Current user profile
│
├── cameras/
│   ├── GET    /               → List cameras
│   ├── POST   /               → Create camera
│   ├── GET    /{id}           → Get camera
│   ├── PUT    /{id}           → Update camera
│   ├── DELETE /{id}           → Delete camera
│   ├── POST   /{id}/start    → Start processing
│   └── POST   /{id}/stop     → Stop processing
│
├── streams/
│   ├── WS     /{camera_id}/live → Live video WebSocket
│   └── GET    /status         → All stream statuses
│
├── incidents/
│   ├── GET    /               → List (paginated, filterable)
│   ├── GET    /{id}           → Get with detections
│   ├── PUT    /{id}/status    → Update status
│   ├── POST   /               → Manual creation
│   ├── GET    /{id}/evidence  → Get evidence list
│   └── GET    /{id}/detections → Get detection list
│
├── alerts/
│   ├── GET    /               → List (paginated)
│   ├── PUT    /{id}/acknowledge → Acknowledge
│   └── WS     /live           → Real-time alert stream
│
├── analytics/
│   ├── GET    /summary        → Overall KPIs
│   ├── GET    /detections/timeline → Time series
│   ├── GET    /incidents/by-camera → Camera distribution
│   └── GET    /incidents/by-severity → Severity distribution
│
├── config/
│   ├── GET    /detection      → Detection params
│   ├── PUT    /detection      → Update detection params
│   ├── GET    /scoring        → Scoring weights
│   └── PUT    /scoring        → Update scoring weights
│
├── audit/
│   └── GET    /logs           → Audit log (admin only)
│
└── GET /health                → System health check
```

### 7.3 Request/Response Formats

#### Standard Success Response
```json
{
  "status": "success",
  "data": { ... },
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

#### Standard Error Response
```json
{
  "status": "error",
  "error": {
    "code": "INCIDENT_NOT_FOUND",
    "message": "Incident with ID xyz not found",
    "details": null
  }
}
```

### 7.4 WebSocket Message Formats

#### Live Feed (Binary)
```
Frame: [JPEG binary data]
Metadata (first message after connect):
{
  "type": "stream_info",
  "camera_id": "uuid",
  "resolution": [1280, 720],
  "fps": 15
}
```

#### Alert Stream (JSON)
```json
{
  "type": "new_alert",
  "data": {
    "alert_id": "uuid",
    "incident_id": "uuid",
    "severity": "critical",
    "message": "Handgun detected - Camera: Lobby Entrance",
    "camera_name": "Lobby Entrance",
    "risk_score": 0.85,
    "timestamp": "2026-08-17T14:30:00Z"
  }
}
```

### 7.5 Rate Limiting

| Endpoint Group | Limit | Window |
|---------------|-------|--------|
| /auth/login | 5 requests | 1 minute |
| /auth/register | 3 requests | 5 minutes |
| General API | 100 requests | 1 minute |
| Analytics | 30 requests | 1 minute |
| WebSocket connect | 10 connections | per user |

---

## 8. Authentication Architecture

### 8.1 Authentication Flow

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Client  │                    │  Backend │                    │    DB    │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  POST /auth/login             │                               │
     │  {email, password}            │                               │
     │──────────────────────────────►│                               │
     │                               │  SELECT user WHERE email=...  │
     │                               │──────────────────────────────►│
     │                               │◄──────────────────────────────│
     │                               │                               │
     │                               │  bcrypt.verify(password, hash)│
     │                               │  ──────────── (internal) ──── │
     │                               │                               │
     │                               │  Generate JWT (access + refresh)
     │                               │  ──────────── (internal) ──── │
     │                               │                               │
     │  200: {access_token,          │                               │
     │        refresh_token,         │                               │
     │        token_type, expires_in}│                               │
     │◄──────────────────────────────│                               │
     │                               │                               │
     │  GET /api/v1/incidents        │                               │
     │  Header: Bearer <access_token>│                               │
     │──────────────────────────────►│                               │
     │                               │  Decode JWT → user_id, role   │
     │                               │  Check role permissions       │
     │                               │  ──────────── (internal) ──── │
     │                               │                               │
     │  200: {incidents: [...]}      │                               │
     │◄──────────────────────────────│                               │
     │                               │                               │
     │  (When access_token expires)  │                               │
     │  POST /auth/refresh           │                               │
     │  {refresh_token}              │                               │
     │──────────────────────────────►│                               │
     │                               │  Validate refresh_token       │
     │                               │  Issue new access_token       │
     │                               │                               │
     │  200: {access_token, ...}     │                               │
     │◄──────────────────────────────│                               │
```

### 8.2 Token Structure

#### Access Token (JWT)
```json
{
  "sub": "user-uuid",
  "email": "operator@example.com",
  "role": "operator",
  "iat": 1692300000,
  "exp": 1692301800,
  "type": "access"
}
```

#### Refresh Token (JWT)
```json
{
  "sub": "user-uuid",
  "iat": 1692300000,
  "exp": 1692904800,
  "type": "refresh"
}
```

### 8.3 WebSocket Authentication

```
1. Client connects to WS endpoint with token query param:
   ws://host/api/v1/streams/{camera_id}/live?token=<jwt>

2. Server validates JWT on connection handshake
3. If invalid → close connection with code 4001 (Unauthorized)
4. If valid → connection accepted, frames begin streaming
5. Token expiry during connection → server sends close frame with code 4002
6. Client must reconnect with new token
```

### 8.4 RBAC Enforcement

| Layer | Mechanism |
|-------|-----------|
| Route level | FastAPI Depends() with role checker |
| Service level | User context passed to service; service validates authorization for specific resources |
| Frontend | Route guards (ProtectedRoute component), UI element visibility based on role |

### 8.5 Security Measures

| Measure | Implementation |
|---------|---------------|
| Password storage | bcrypt (cost=12) |
| Token signing | HS256 with 256-bit secret from env |
| Token transport | Authorization: Bearer header (not cookies) |
| Rate limiting | Redis-based sliding window |
| Input validation | Pydantic models with field constraints |
| SQL injection | SQLAlchemy ORM (parameterized queries) |
| XSS prevention | React (auto-escapes), Content-Security-Policy header |
| CORS | Whitelist frontend origin only |

---

## 9. Evidence Storage Architecture

### 9.1 Storage Layout

```
evidence/                          (Docker volume mount)
├── snapshots/
│   ├── 2026/
│   │   ├── 08/
│   │   │   ├── 17/
│   │   │   │   ├── {incident_id}_{timestamp}.jpg
│   │   │   │   ├── {incident_id}_{timestamp}.jpg
│   │   │   │   └── ...
│   │   │   └── 18/
│   │   └── 09/
│   └── ...
├── clips/
│   ├── 2026/
│   │   ├── 08/
│   │   │   ├── 17/
│   │   │   │   ├── {incident_id}_{timestamp}.mp4
│   │   │   │   └── ...
│   │   │   └── ...
│   │   └── ...
│   └── ...
└── temp/                          (Temporary files during processing)
```

### 9.2 Evidence Capture Flow

```
Incident Created
       │
       ├──────────────────────────────────┐
       ▼                                  ▼
┌──────────────┐                 ┌──────────────────┐
│ Snapshot     │                 │ Clip Capture     │
│ Capture      │                 │                  │
│              │                 │ 1. Read ring     │
│ 1. Get frame │                 │    buffer (last  │
│ 2. Annotate  │                 │    10s of frames)│
│    (bboxes)  │                 │ 2. Continue      │
│ 3. Apply     │                 │    recording 10s │
│    privacy   │                 │ 3. Apply privacy │
│    filter    │                 │    to each frame │
│ 4. Encode    │                 │ 4. Encode to MP4 │
│    JPEG      │                 │    (H.264)       │
│ 5. Write to  │                 │ 5. Write to disk │
│    disk      │                 │                  │
└──────┬───────┘                 └────────┬─────────┘
       │                                  │
       └──────────────┬───────────────────┘
                      │
                      ▼
            ┌──────────────────┐
            │ Create Evidence  │
            │ DB Record        │
            │ (file_path,      │
            │  type, size,     │
            │  incident_id)    │
            └──────────────────┘
```

### 9.3 Evidence Component Specification

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Capture, persist, and serve evidence media files with privacy enforcement |
| **Inputs** | Capture command (incident_id, frame_buffer, current_frame), retrieval requests (incident_id) |
| **Outputs** | JPEG files (snapshots, ~50-200KB), MP4 files (clips, ~2-10MB), DB metadata records |
| **Dependencies** | OpenCV (imencode, VideoWriter), Privacy Filter, File System, PostgreSQL |
| **Failure Cases** | See below |

| Failure | Handling |
|---------|----------|
| Disk full | Check available space before write; if <100MB → skip capture, log CRITICAL, mark incident as evidence_failed |
| Frame buffer incomplete | Capture available frames; record actual duration in metadata |
| Video encoding fails | Retry with reduced quality; if still fails → save individual frames as fallback |
| Privacy filter fails | Store with `anonymized=false` flag; queue for retry |
| File system permission error | Log error; attempt alternate temp directory |

### 9.4 Retention & Cleanup

| Aspect | Details |
|--------|---------|
| Retention period | Configurable (default: 90 days) |
| Cleanup schedule | Daily at 02:00 UTC (background task) |
| Cleanup process | 1) Query evidence records older than retention. 2) Delete files. 3) Delete DB records. 4) Log cleanup summary |
| Manual purge | Admin API endpoint to purge specific incident evidence |
| Disk monitoring | Health endpoint reports available evidence storage space |

---

## 10. Logging Architecture

### 10.1 Log Levels & Usage

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Detailed pipeline state, frame-level info | "Frame 12345 processed: 3 detections, 2 tracked" |
| INFO | Normal operations, lifecycle events | "Camera lobby-01 connected", "Incident INC-001 created" |
| WARNING | Degraded performance, recoverable issues | "Camera reconnecting (attempt 2)", "GPU memory high" |
| ERROR | Operation failures requiring attention | "Evidence capture failed for INC-002", "DB connection timeout" |
| CRITICAL | System-level failures | "All cameras disconnected", "Disk full", "Detection model failed to load" |

### 10.2 Log Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOG SOURCES                                   │
│                                                                     │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐   │
│  │ FastAPI   │  │ Detection │  │ Services  │  │  Middleware   │   │
│  │ Routes    │  │ Pipeline  │  │           │  │  (requests)   │   │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └──────┬────────┘   │
│        │               │               │               │            │
└────────┼───────────────┼───────────────┼───────────────┼────────────┘
         │               │               │               │
         └───────────────┼───────────────┼───────────────┘
                         │               │
                         ▼               ▼
              ┌──────────────────────────────────┐
              │     Python logging (structlog)    │
              │                                  │
              │  Formatters:                     │
              │  • JSON (production)             │
              │  • Console/colored (development) │
              └──────────┬───────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
     ┌──────────┐ ┌──────────┐ ┌──────────────┐
     │  stdout  │ │  File    │ │  Audit DB    │
     │ (Docker  │ │ (rotate) │ │ (user actions│
     │  logs)   │ │          │ │  only)       │
     └──────────┘ └──────────┘ └──────────────┘
```

### 10.3 Structured Log Format (JSON)

```json
{
  "timestamp": "2026-08-17T14:30:00.123Z",
  "level": "INFO",
  "logger": "app.services.incident_service",
  "message": "Incident created",
  "context": {
    "incident_id": "uuid-123",
    "camera_id": "uuid-456",
    "severity": "high",
    "risk_score": 0.72
  },
  "request_id": "req-789",
  "user_id": null,
  "duration_ms": 45
}
```

### 10.4 Log Component Specification

| Attribute | Details |
|-----------|---------|
| **Responsibility** | Provide structured, queryable logging across all system components with appropriate routing (stdout, file, audit DB) |
| **Inputs** | Log calls from application code with level, message, and structured context |
| **Outputs** | JSON-formatted log entries to stdout (Docker), rotating files, and audit_logs table (for user actions) |
| **Dependencies** | Python structlog library, PostgreSQL (for audit), file system (for file logs) |
| **Failure Cases** | 1) File system full → fallback to stdout only. 2) DB unavailable for audit → buffer in memory (max 1000 entries), retry. 3) Log write exception → never propagate to caller (logging must not break application flow) |

### 10.5 Audit Log vs Application Log

| Aspect | Application Log | Audit Log |
|--------|----------------|-----------|
| Purpose | Debugging, operations, monitoring | Compliance, accountability |
| Storage | File + stdout | PostgreSQL (audit_logs table) |
| Content | Technical events | User actions with before/after |
| Retention | 30 days (file rotation) | Permanent (or per policy) |
| Access | DevOps/Admin | Admin only (via API) |
| Immutability | Overwritten by rotation | Append-only (no UPDATE/DELETE) |

### 10.6 Request Correlation

Every API request is assigned a unique `request_id` (UUID) that:
1. Is generated at the middleware layer
2. Is attached to all log entries during that request
3. Is returned in the response header `X-Request-ID`
4. Allows end-to-end tracing from frontend error → backend log

---

## 11. Error-Handling Architecture

### 11.1 Error Categories

| Category | HTTP Code | Examples | Recovery |
|----------|-----------|----------|----------|
| Validation | 422 | Invalid input, missing fields | Client fixes input |
| Authentication | 401 | Invalid/expired token | Client re-authenticates |
| Authorization | 403 | Insufficient role permissions | None (design-time) |
| Not Found | 404 | Invalid resource ID | Client uses valid ID |
| Conflict | 409 | Duplicate email, invalid state transition | Client resolves conflict |
| Rate Limited | 429 | Too many requests | Client retries after delay |
| Internal | 500 | Unhandled exception, DB failure | Ops investigates |
| Service Unavailable | 503 | Detection pipeline down, Redis down | System recovers |

### 11.2 Error Response Format

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "value": "not-an-email"
      }
    ]
  },
  "request_id": "req-uuid-123"
}
```

### 11.3 Error Code Registry

| Code | Category | Meaning |
|------|----------|---------|
| AUTH_INVALID_CREDENTIALS | Auth | Wrong email/password |
| AUTH_TOKEN_EXPIRED | Auth | JWT access token expired |
| AUTH_TOKEN_INVALID | Auth | Malformed or tampered token |
| AUTH_INSUFFICIENT_ROLE | AuthZ | Role lacks permission |
| VALIDATION_ERROR | Input | Pydantic validation failed |
| RESOURCE_NOT_FOUND | Data | Entity ID doesn't exist |
| RESOURCE_CONFLICT | Data | Duplicate unique field |
| INCIDENT_INVALID_TRANSITION | Business | Invalid status change |
| CAMERA_CONNECTION_FAILED | External | Cannot reach camera URL |
| DETECTION_MODEL_ERROR | AI | Model inference failed |
| EVIDENCE_CAPTURE_FAILED | Storage | Could not save evidence |
| RATE_LIMIT_EXCEEDED | Security | Too many requests |
| INTERNAL_ERROR | System | Unhandled server error |
| SERVICE_UNAVAILABLE | System | Dependent service down |

### 11.4 Error Handling Flow

```
Exception Occurs
       │
       ▼
┌──────────────────┐     Known Exception?
│ Exception Handler│────── YES ──→ Map to error code + HTTP status
│ (Middleware)     │              → Create structured error response
│                  │              → Log at appropriate level
│                  │              → Return to client
│                  │
│                  │────── NO ───→ Log at ERROR level with stack trace
│                  │              → Return generic 500 with request_id
│                  │              → Do NOT expose internal details
└──────────────────┘
```

### 11.5 Layer-Specific Error Handling

#### API Layer (Routers)
| Behavior | Details |
|----------|---------|
| Input validation fails | FastAPI/Pydantic auto-returns 422 with field details |
| Service raises known exception | Caught by exception handler middleware |
| Unhandled exception | Global handler returns 500, logs full traceback |

#### Service Layer
| Behavior | Details |
|----------|---------|
| DB operation fails | Raise specific exception (e.g., `IncidentNotFoundError`) |
| External service unavailable | Raise `ServiceUnavailableError` with context |
| Business rule violation | Raise `BusinessLogicError` with explanation |
| Never catch broad Exception | Let it propagate to global handler |

#### Detection Pipeline
| Behavior | Details |
|----------|---------|
| Frame read failure | Log warning, skip frame, continue loop |
| Inference error | Log error, skip frame, increment error counter; if >10 consecutive → pause pipeline |
| Tracking error | Reset tracker state, log error, continue |
| Redis publish failure | Buffer message, retry with backoff |

#### Frontend
| Behavior | Details |
|----------|---------|
| API returns 401 | Interceptor triggers token refresh; if refresh fails → redirect to login |
| API returns 403 | Show "Access Denied" toast notification |
| API returns 422 | Display field-level validation errors in form |
| API returns 500 | Show generic error toast with request_id for support |
| WebSocket disconnects | Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s) |
| Network offline | Show offline banner; queue actions for retry |

### 11.6 Circuit Breaker Pattern

For communication between the backend and the detection pipeline:

```
States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery)

CLOSED:
  - All requests pass through
  - Track failure count
  - If failures > threshold (5) in window (60s) → transition to OPEN

OPEN:
  - All requests immediately fail with ServiceUnavailableError
  - After cooldown (30s) → transition to HALF_OPEN

HALF_OPEN:
  - Allow 1 test request through
  - If success → transition to CLOSED
  - If failure → transition to OPEN
```

Applied to:
- Detection pipeline → Backend communication (Redis)
- Backend → PostgreSQL (connection pool with health checks)
- Backend → Redis (reconnection with backoff)

### 11.7 Graceful Degradation

| Component Down | System Behavior |
|----------------|-----------------|
| Redis | Alerts still created in DB; WebSocket push uses direct connection; no caching |
| Detection pipeline | Dashboard shows "Detection Offline"; existing incidents still manageable |
| One camera | Other cameras continue; disconnected camera shows "Offline" |
| PostgreSQL | All writes fail; return 503; detection pipeline continues but can't persist |
| Frontend assets | Nginx serves cached version; fallback to basic HTML error page |

---

## Summary

This architecture document defines 11 major architectural concerns with detailed specifications for every component. Key design decisions:

1. **Separation of detection and API** — The AI pipeline runs as an independent process communicating via Redis, preventing inference delays from blocking API responses.

2. **Ring buffer for evidence** — Pre-incident frames are always available in memory, enabling "look-back" clip capture without filesystem overhead.

3. **WebSocket for real-time** — Both video streaming and alert delivery use WebSocket for sub-second latency.

4. **Optimistic locking** — Incident status updates use version columns to prevent concurrent update conflicts.

5. **Circuit breaker** — Prevents cascade failures when dependent services go down.

6. **Structured logging with correlation** — Every request can be traced end-to-end using request_id.

---

**This document is ready for implementation. Awaiting approval to begin Phase 1: Foundation.**
