# Software Requirements Specification (SRS)

## AI-Based Real-Time Threat Detection and Emergency Response Platform

| Document Info | |
|---|---|
| **Version** | 1.0 |
| **Date** | August 17, 2026 |
| **Status** | Approved |
| **Classification** | Academic Project – B.Tech Final Year |

---

## Table of Contents

1. [Project Objective](#1-project-objective)
2. [Problem Statement](#2-problem-statement)
3. [Scope](#3-scope)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [User Roles](#6-user-roles)
7. [System Constraints](#7-system-constraints)
8. [Assumptions](#8-assumptions)
9. [Security Requirements](#9-security-requirements)
10. [Privacy Requirements](#10-privacy-requirements)
11. [AI/ML Requirements](#11-aiml-requirements)
12. [Acceptance Criteria](#12-acceptance-criteria)
13. [Requirements Traceability Structure](#13-requirements-traceability-structure)

---

## 1. Project Objective

To design and develop an AI-powered real-time threat detection and emergency response platform that uses computer vision (YOLO-based object detection) to identify weapons in live video feeds, assess threat levels through configurable scoring, and provide security operators with actionable alerts, incident management, and historical analytics through a web-based dashboard.

The platform serves as an academic prototype demonstrating the integration of deep learning, real-time video processing, full-stack web development, and production-grade software engineering practices.

---

## 2. Problem Statement

Traditional physical security monitoring relies on human operators continuously watching multiple camera feeds — an approach that suffers from attention fatigue, delayed response times, and inability to scale. Critical moments where weapons become visible may be missed entirely, resulting in delayed emergency response.

Current challenges include:
- Human operators cannot maintain consistent attention across multiple video feeds for extended periods
- Manual monitoring introduces delays between threat appearance and alert generation
- No systematic evidence capture occurs at the moment of detection
- Historical incident data is not leveraged for pattern analysis
- Existing AI detection systems often generate excessive false positives, leading to alert fatigue

This platform addresses these gaps by providing automated weapon detection with multi-frame verification, configurable threat scoring, real-time alerting, and comprehensive incident management — all designed to assist (not replace) human security operators.

---

## 3. Scope

### 3.1 In Scope

| Area | Description |
|------|-------------|
| Video Input | Live webcam feeds (USB/IP/RTSP) and uploaded video files |
| AI Detection | YOLO-based weapon detection (handgun, rifle, knife) and person detection |
| Object Tracking | Persistent identity assignment across frames |
| Alert System | Real-time threat alerts with severity classification |
| Incident Management | Full incident lifecycle with evidence capture |
| Web Dashboard | Live monitoring, incident management, analytics |
| Authentication | JWT-based auth with role-based access control |
| Privacy | Face anonymization on stored evidence |
| Deployment | Docker Compose-based containerized deployment |
| Database | PostgreSQL for persistent storage |
| Audit | Complete audit trail of user and system actions |

### 3.2 Out of Scope

| Area | Reason |
|------|--------|
| Behavioral prediction | System does not predict intent; only detects observable weapons |
| Horizontal scaling | Single-node deployment for academic prototype |
| Mobile applications | Web dashboard only; no native mobile apps |
| Third-party integrations | No integration with law enforcement systems, SMS gateways, or external APIs |
| Model training pipeline | Uses pre-trained/fine-tuned weights; training infrastructure not included |
| High availability | No failover, redundancy, or disaster recovery |
| Edge deployment | Processing occurs on server; no edge/camera-embedded inference |

---

## 4. Functional Requirements

### 4.1 Video Input & Stream Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | The system shall accept live video input from USB webcams via OpenCV VideoCapture | High |
| FR-002 | The system shall accept live video input from IP cameras via RTSP stream URLs | High |
| FR-003 | The system shall accept uploaded video files in MP4, AVI, and MKV formats for analysis | Medium |
| FR-004 | The system shall support processing of at least 4 simultaneous camera streams | High |
| FR-005 | The system shall allow operators to start, stop, and pause processing on individual camera streams | High |
| FR-006 | The system shall monitor and report stream health metrics including current FPS, connection status, and frame drop count | Medium |
| FR-007 | The system shall automatically attempt reconnection when a camera stream disconnects, with configurable retry intervals | Medium |

### 4.2 AI Detection

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-008 | The system shall detect weapons (handgun, rifle, knife) in video frames using a YOLO-based object detection model | High |
| FR-009 | The system shall detect persons in video frames and generate bounding boxes for each detected person | High |
| FR-010 | The system shall output a confidence score (0.0–1.0) for each detection | High |
| FR-011 | The system shall output bounding box coordinates (x, y, width, height) for each detection | High |
| FR-012 | The system shall apply Non-Maximum Suppression (NMS) to eliminate duplicate overlapping detections | High |
| FR-013 | The system shall allow configuration of the minimum confidence threshold for detections (default: 0.5) | High |

### 4.3 Object Tracking

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-014 | The system shall assign a unique persistent track ID to each detected object across consecutive frames | High |
| FR-015 | The system shall maintain object identity when objects temporarily overlap or are partially occluded | Medium |
| FR-016 | The system shall record the age (number of frames / duration) of each active track | High |
| FR-017 | The system shall remove tracks that have not been associated with a detection for a configurable number of frames (default: 30) | Medium |

### 4.4 Multi-Frame Verification

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-018 | The system shall require a weapon detection to appear in at least N out of M consecutive frames before confirming it as a verified threat (default: N=3, M=5) | High |
| FR-019 | The system shall not generate any incident or alert for detections that fail multi-frame verification | High |
| FR-020 | The system shall allow administrators to configure the N and M parameters for multi-frame verification | Medium |
| FR-021 | The system shall compute the average confidence score across verified detection frames | Medium |

### 4.5 Threat Scoring

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-022 | The system shall compute a numerical risk score (0.0–1.0) for each verified threat based on configurable weighted factors | High |
| FR-023 | The scoring factors shall include: weapon type, average confidence, proximity to nearest person, duration of visibility, and number of weapons detected | High |
| FR-024 | The system shall map the computed risk score to a severity level: Low (0.0–0.3), Medium (0.3–0.5), High (0.5–0.7), Critical (0.7–1.0) | High |
| FR-025 | The system shall allow administrators to configure the weights for each scoring factor | Medium |
| FR-026 | The system shall allow administrators to configure the threshold at which an incident is automatically created | Medium |

### 4.6 Incident Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-027 | The system shall automatically create an incident record when a verified threat's risk score exceeds the configured threshold | High |
| FR-028 | Each incident shall contain: incident ID, camera ID, severity level, risk score, start timestamp, status, and description | High |
| FR-029 | The system shall support incident status transitions: Open → Acknowledged → Resolved → Closed | High |
| FR-030 | The system shall allow authorized users to manually update incident status with mandatory notes | Medium |
| FR-031 | The system shall allow operators to manually create incidents with camera selection and description | Medium |
| FR-032 | The system shall associate all related detections with their parent incident | High |
| FR-033 | The system shall record the timestamp when each status transition occurs | Medium |

### 4.7 Evidence Capture

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-034 | The system shall capture and store an annotated snapshot (JPEG) of the frame at the moment of incident creation | High |
| FR-035 | The annotated snapshot shall include bounding boxes, class labels, confidence scores, and timestamp overlay | High |
| FR-036 | The system shall capture and store a short video clip surrounding the incident (configurable duration, default: 10 seconds before + 10 seconds after) | Medium |
| FR-037 | Each evidence item shall be linked to its parent incident and include capture timestamp and file path | High |
| FR-038 | The system shall support retrieval of evidence items by incident ID | High |

### 4.8 Camera/Location Metadata

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-039 | The system shall allow administrators to register cameras with: name, location description, stream URL, and metadata | High |
| FR-040 | The system shall allow administrators to update camera configuration | Medium |
| FR-041 | The system shall allow administrators to remove cameras from the system | Medium |
| FR-042 | Each incident and detection shall reference the source camera ID | High |
| FR-043 | The system shall display camera status (online/offline/processing) in real-time | Medium |

### 4.9 Alert Management

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-044 | The system shall generate a real-time alert for every new incident | High |
| FR-045 | Each alert shall contain: alert ID, incident reference, severity level, message text, and creation timestamp | High |
| FR-046 | The system shall push alerts to all connected dashboard clients via WebSocket within 1 second of generation | High |
| FR-047 | The system shall allow operators to acknowledge alerts | High |
| FR-048 | The system shall maintain a persistent history of all alerts with their acknowledgement status | Medium |
| FR-049 | The system shall display unacknowledged alert count as a badge in the dashboard | Low |

### 4.10 Web Dashboard – Live Monitoring

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-050 | The dashboard shall display live video feeds from active cameras with detection overlays (bounding boxes, labels) | High |
| FR-051 | The dashboard shall support viewing multiple camera feeds simultaneously in a grid layout | High |
| FR-052 | The dashboard shall display a real-time alert panel showing the most recent alerts with severity indicators | High |
| FR-053 | The dashboard shall display system health status: number of active cameras, average detection FPS, and system uptime | Medium |
| FR-054 | The dashboard shall allow users to select and view a single camera feed in full-screen mode | Medium |

### 4.11 Web Dashboard – Historical Analytics

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-055 | The dashboard shall display detection count statistics over configurable time periods (daily, weekly, monthly) | Medium |
| FR-056 | The dashboard shall display incident distribution by camera/location | Medium |
| FR-057 | The dashboard shall display incident distribution by severity level | Medium |
| FR-058 | The dashboard shall display a timeline chart of detection/incident events | Medium |
| FR-059 | The dashboard shall allow export of incident reports in CSV format | Low |
| FR-060 | The dashboard shall allow export of incident reports in PDF format | Low |

### 4.12 Authentication & Role-Based Access

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-061 | The system shall require authentication for all API endpoints except login and health check | High |
| FR-062 | The system shall support user registration with email and password | High |
| FR-063 | The system shall authenticate users and issue JWT access tokens with configurable expiration | High |
| FR-064 | The system shall support token refresh without requiring re-authentication | Medium |
| FR-065 | The system shall enforce role-based access control with three roles: Admin, Operator, Viewer | High |
| FR-066 | Admin role shall have full access to all features including user management and system configuration | High |
| FR-067 | Operator role shall have access to monitoring, incident management, and alert acknowledgement | High |
| FR-068 | Viewer role shall have read-only access to dashboard, incidents, and analytics | High |

### 4.13 Logging & Audit Trail

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-069 | The system shall log all user actions (login, logout, incident status changes, configuration changes) with user ID and timestamp | High |
| FR-070 | The system shall log all detection events with camera ID, detection class, confidence, and timestamp | Medium |
| FR-071 | The system shall provide an audit log viewing interface accessible only to Admin users | Medium |
| FR-072 | Audit log entries shall be immutable (append-only) | High |

### 4.14 System Configuration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-073 | The system shall provide a configuration interface for detection parameters (confidence threshold, NMS threshold) | Medium |
| FR-074 | The system shall provide a configuration interface for threat scoring weights | Medium |
| FR-075 | The system shall provide a configuration interface for multi-frame verification parameters (N and M values) | Medium |
| FR-076 | Configuration changes shall take effect without requiring system restart | Medium |
| FR-077 | All configuration changes shall be recorded in the audit log | Medium |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR-001 | The system shall process video frames at ≥15 FPS per stream on hardware with a dedicated GPU (NVIDIA GTX 1060 or equivalent) | Measured via stream health metrics |
| NFR-002 | The system shall process video frames at ≥5 FPS per stream on CPU-only hardware | Measured via stream health metrics |
| NFR-003 | Alert generation latency shall not exceed 3 seconds from first weapon frame appearance to alert delivery at dashboard | Measured from frame timestamp to WebSocket message receipt |
| NFR-004 | API response time for CRUD operations shall not exceed 500ms for 95th percentile requests | Measured under 50 concurrent users |
| NFR-005 | The dashboard shall render initial page load within 2 seconds on a standard broadband connection | Measured via browser performance API |
| NFR-006 | WebSocket frame delivery to dashboard clients shall not exceed 200ms latency from server emission | Measured via timestamp comparison |

### 5.2 Scalability

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR-007 | The system shall support at least 4 simultaneous camera streams with full detection pipeline | Verified via multi-stream test |
| NFR-008 | The system shall support up to 8 simultaneous streams with graceful FPS reduction | Verified via load test |
| NFR-009 | The system shall support at least 50 concurrent dashboard users | Verified via load test tool |

### 5.3 Reliability

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR-010 | The system shall not generate alerts for detections that fail multi-frame verification (zero false-alert tolerance for unverified detections) | Verified via automated test suite |
| NFR-011 | The system shall continue operating remaining streams if one camera stream disconnects | Verified via fault injection test |
| NFR-012 | The system shall persist all incident data and evidence to disk before confirming creation to the user | Verified via crash recovery test |
| NFR-013 | The system shall automatically reconnect to disconnected camera streams with exponential backoff | Verified via network disruption test |

### 5.4 Usability

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR-014 | All dashboard pages shall be responsive and usable on screen widths from 1024px to 2560px | Verified via responsive design testing |
| NFR-015 | Alert severity shall be visually distinguishable using color coding (green/yellow/orange/red) | Verified via UI review |
| NFR-016 | Critical alerts shall include audio notification in the dashboard | Verified via functional test |
| NFR-017 | The system shall provide meaningful error messages for all user-facing error conditions | Verified via error scenario testing |

### 5.5 Maintainability

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR-018 | The codebase shall maintain separation of concerns through layered architecture (API, Service, Data, Detection) | Verified via code review |
| NFR-019 | All API endpoints shall be documented via auto-generated OpenAPI specification | Verified via /docs endpoint |
| NFR-020 | Database schema changes shall be managed through versioned migrations | Verified via Alembic migration history |
| NFR-021 | Backend business logic shall achieve ≥80% unit test coverage | Measured via coverage tool |

### 5.6 Portability

| ID | Requirement | Metric |
|----|-------------|--------|
| NFR-022 | The complete system shall be deployable via a single `docker-compose up` command | Verified via clean deployment test |
| NFR-023 | The system shall run on Linux (Ubuntu 22.04+) and Windows 10+ with Docker Desktop | Verified via cross-platform deployment |
| NFR-024 | No hard-coded file paths or platform-specific assumptions shall exist in application code | Verified via code review |

---

## 6. User Roles

### 6.1 Role Definitions

| Role | Description | User Count (Expected) |
|------|-------------|----------------------|
| **Admin** | System administrator responsible for user management, system configuration, camera management, and full platform access | 1-2 |
| **Operator** | Security personnel responsible for monitoring live feeds, responding to alerts, managing incidents, and reviewing evidence | 3-10 |
| **Viewer** | Supervisory or reporting personnel with read-only access to dashboards, incident history, and analytics | 5-20 |

### 6.2 Permission Matrix

| Feature | Admin | Operator | Viewer |
|---------|-------|----------|--------|
| View live feeds | ✓ | ✓ | ✓ |
| View alerts | ✓ | ✓ | ✓ |
| Acknowledge alerts | ✓ | ✓ | ✗ |
| View incidents | ✓ | ✓ | ✓ |
| Update incident status | ✓ | ✓ | ✗ |
| Create manual incidents | ✓ | ✓ | ✗ |
| View evidence | ✓ | ✓ | ✓ |
| View analytics | ✓ | ✓ | ✓ |
| Export reports | ✓ | ✓ | ✓ |
| Manage cameras (CRUD) | ✓ | ✗ | ✗ |
| Start/stop streams | ✓ | ✓ | ✗ |
| Manage users | ✓ | ✗ | ✗ |
| Configure detection params | ✓ | ✗ | ✗ |
| Configure scoring weights | ✓ | ✗ | ✗ |
| View audit logs | ✓ | ✗ | ✗ |

---

## 7. System Constraints

| ID | Constraint | Rationale |
|----|-----------|-----------|
| CON-001 | The system shall use PostgreSQL 15 as the primary relational database | Project requirement; strong JSON support and reliability |
| CON-002 | The backend shall be implemented using Python 3.10+ with FastAPI framework | Project requirement; async performance and auto-generated docs |
| CON-003 | The frontend shall be implemented using React 18+ with TypeScript | Project requirement; type safety and component ecosystem |
| CON-004 | The AI detection model shall be based on the YOLO architecture (v8 or v9) via the Ultralytics library | Project requirement; state-of-art single-stage detector |
| CON-005 | The system shall be deployable via Docker Compose | Project requirement; reproducible deployment |
| CON-006 | The system is designed for single-node deployment (no distributed architecture) | Academic prototype scope limitation |
| CON-007 | Maximum video resolution processed shall be 1920×1080; frames resized to 640×640 for inference | GPU memory and performance constraint |
| CON-008 | Evidence video clips shall not exceed 30 seconds in duration | Storage constraint |
| CON-009 | The system shall operate within a single local network or localhost environment | Academic demonstration scope |
| CON-010 | YOLO model weights file size shall not exceed 200MB | Container image size and startup time |

---

## 8. Assumptions

| ID | Assumption | Impact if Invalid |
|----|-----------|-------------------|
| ASM-001 | The deployment environment has a CUDA-compatible NVIDIA GPU for production-level FPS | System will fallback to CPU mode with reduced FPS (NFR-002) |
| ASM-002 | Camera streams provide stable video at ≥15 FPS with ≥720p resolution | Lower quality input will degrade detection accuracy |
| ASM-003 | Network bandwidth between cameras and server is sufficient for video streaming (≥5 Mbps per stream) | Frame drops and degraded detection will occur |
| ASM-004 | Pre-trained or fine-tuned YOLO weights are available for weapon classes | System cannot detect weapons without appropriate model weights |
| ASM-005 | Docker and Docker Compose are available on the deployment machine | System cannot be deployed without containerization platform |
| ASM-006 | Users access the dashboard via modern browsers (Chrome 90+, Firefox 90+, Edge 90+) | UI may not render correctly on older browsers |
| ASM-007 | Sufficient disk storage (≥50GB) is available for evidence and database | Evidence capture will fail when storage is exhausted |
| ASM-008 | The system operates in environments where video surveillance is legally authorized | Legal compliance is the operator's responsibility |
| ASM-009 | At least one admin user is seeded during initial deployment | System cannot be configured without admin access |
| ASM-010 | Weapons in the training dataset are representative of real-world appearances | Model may miss weapons not represented in training data |

---

## 9. Security Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SEC-001 | All user passwords shall be hashed using bcrypt with a minimum cost factor of 12 before storage | High |
| SEC-002 | JWT access tokens shall expire after a configurable period (default: 30 minutes) | High |
| SEC-003 | JWT refresh tokens shall expire after a configurable period (default: 7 days) | High |
| SEC-004 | All API endpoints (except /health and /auth/login) shall require a valid JWT access token | High |
| SEC-005 | The system shall enforce role-based authorization on every API endpoint | High |
| SEC-006 | Failed login attempts shall be rate-limited to 5 attempts per minute per IP address | Medium |
| SEC-007 | All database credentials, JWT secrets, and API keys shall be stored in environment variables, never in source code | High |
| SEC-008 | The system shall validate and sanitize all user inputs to prevent SQL injection and XSS attacks | High |
| SEC-009 | CORS shall be configured to allow only specified frontend origins | Medium |
| SEC-010 | WebSocket connections shall require authentication via token parameter | High |
| SEC-011 | Evidence file paths shall be generated by the system; user-supplied paths shall not be used for file access | High |
| SEC-012 | The system shall log all authentication events (login success, login failure, token refresh) in the audit trail | High |
| SEC-013 | Admin operations (user management, configuration changes) shall require re-authentication if the session is older than 15 minutes | Low |
| SEC-014 | The system shall not expose stack traces or internal error details in API responses in production mode | Medium |

---

## 10. Privacy Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| PRV-001 | The system shall apply face blurring (Gaussian blur, σ≥15) to all faces detected in evidence snapshots before storage | High |
| PRV-002 | The system shall apply face blurring to all faces in evidence video clips before storage | High |
| PRV-003 | Face anonymization shall be configurable (enable/disable) at the system level by administrators | Medium |
| PRV-004 | Live feed streams to the dashboard shall NOT have face anonymization applied (operators need full visual context for monitoring) | High |
| PRV-005 | The system shall not store raw biometric data (face embeddings, fingerprints) | High |
| PRV-006 | Evidence data shall be subject to a configurable retention period (default: 90 days) after which it is automatically deleted | Medium |
| PRV-007 | The system shall provide a mechanism for administrators to manually purge evidence for specific incidents | Medium |
| PRV-008 | The system shall not perform facial recognition, person re-identification, or behavioral profiling | High |
| PRV-009 | Audit logs shall not contain video frame data or detection images | Medium |
| PRV-010 | Database exports shall not include password hashes or security tokens | High |

---

## 11. AI/ML Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| AI-001 | The detection model shall be based on YOLOv8 (medium or larger) or YOLOv9 architecture | High |
| AI-002 | The model shall detect at minimum 3 weapon classes: handgun, rifle, knife | High |
| AI-003 | The model shall detect the "person" class to enable proximity-based threat scoring | High |
| AI-004 | The model shall achieve a minimum mean Average Precision (mAP@0.5) of 0.60 on the evaluation dataset | High |
| AI-005 | The model inference time shall not exceed 50ms per frame on GPU (NVIDIA GTX 1060 equivalent) | High |
| AI-006 | The model inference time shall not exceed 200ms per frame on CPU | Medium |
| AI-007 | The object tracker shall maintain correct identity assignment for ≥80% of tracked objects across 100 consecutive frames in standard test scenarios | Medium |
| AI-008 | The multi-frame verifier shall eliminate ≥90% of single-frame false positive detections | High |
| AI-009 | The threat scoring engine shall produce repeatable scores (identical inputs → identical outputs) | High |
| AI-010 | The system shall support model weight replacement without code changes (hot-swappable model file) | Medium |
| AI-011 | The detection pipeline shall support configurable input resolution (320×320, 640×640, 1280×1280) | Low |
| AI-012 | The system shall log all raw detections (including those filtered by verification) for offline analysis | Medium |
| AI-013 | The NMS IoU threshold shall be configurable (default: 0.45) | Medium |
| AI-014 | The system shall report model version and configuration in the system health endpoint | Low |
| AI-015 | The detection pipeline shall not make inferences about person intent, behavior, or criminal likelihood | High |

---

## 12. Acceptance Criteria

### AC-1: Video Input & Stream Management

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-001 | Given a connected USB webcam, when stream processing is started, then live frames are captured at ≥15 FPS | Automated test with FPS counter |
| AC-002 | Given a valid RTSP URL, when a camera is added and started, then the system successfully connects and captures frames | Integration test with RTSP simulator |
| AC-003 | Given an uploaded MP4 file, when analysis is triggered, then all frames are processed through the detection pipeline | Automated test with sample video |
| AC-004 | Given 4 active camera streams, when all are processing simultaneously, then each maintains ≥10 FPS on GPU hardware | Performance test |
| AC-005 | Given an active stream, when the operator clicks "stop", then frame processing ceases within 2 seconds | Functional test |
| AC-006 | Given a disconnected camera, when reconnection is configured, then the system retries connection at configured intervals | Fault injection test |

### AC-2: AI Detection

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-007 | Given a video frame containing a handgun, when inference is performed, then the handgun is detected with confidence ≥0.5 | Model evaluation on test dataset |
| AC-008 | Given a video frame containing a person, when inference is performed, then the person is detected with a bounding box | Model evaluation on test dataset |
| AC-009 | Given overlapping detections for the same object, when NMS is applied, then only the highest-confidence detection remains | Unit test with synthetic data |
| AC-010 | Given a confidence threshold of 0.6, when a detection has confidence 0.55, then it is filtered out | Unit test |
| AC-011 | Given the evaluation dataset, when mAP@0.5 is computed, then the result is ≥0.60 | Evaluation script |

### AC-3: Object Tracking

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-012 | Given a weapon moving across 50 consecutive frames, when tracking is applied, then the same track ID is maintained throughout | Integration test with video sequence |
| AC-013 | Given a tracked object that disappears for 10 frames then reappears, when tracking is active, then identity is maintained | Integration test |
| AC-014 | Given a tracked object absent for more than 30 frames, when the timeout expires, then the track is removed | Unit test |

### AC-4: Multi-Frame Verification

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-015 | Given N=3, M=5, when a weapon appears in only 2 out of 5 frames, then no alert is generated | Unit test |
| AC-016 | Given N=3, M=5, when a weapon appears in 3 out of 5 frames, then the detection is verified and passed to threat scoring | Unit test |
| AC-017 | Given a verified detection, when average confidence is computed, then it equals the mean of confidence values across the N verified frames | Unit test |

### AC-5: Threat Scoring

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-018 | Given a verified handgun detection near a person with high confidence over 5 seconds, when scored with default weights, then risk_score > 0.7 (Critical) | Unit test with fixed inputs |
| AC-019 | Given a verified knife detection with no person nearby and low confidence, when scored, then risk_score < 0.3 (Low) | Unit test with fixed inputs |
| AC-020 | Given identical inputs, when scoring is run multiple times, then the output is identical each time | Determinism test |
| AC-021 | Given modified scoring weights via configuration API, when the next detection is scored, then the new weights are applied | Integration test |

### AC-6: Incident Management

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-022 | Given a threat with risk_score above threshold, when the decision engine evaluates it, then an incident record is created in the database | Integration test |
| AC-023 | Given an open incident, when an operator changes status to "Acknowledged", then the status is updated and timestamp recorded | API test |
| AC-024 | Given an incident, when its detail is requested, then all associated detections and evidence items are returned | API test |
| AC-025 | Given an operator with correct permissions, when they create a manual incident, then it is persisted with status "Open" | API test |

### AC-7: Evidence Capture

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-026 | Given an incident creation event, when evidence capture is triggered, then a JPEG snapshot with annotations is saved to disk | Integration test |
| AC-027 | Given the snapshot, when it is viewed, then bounding boxes, labels, confidence, and timestamp are visible | Visual verification / image analysis test |
| AC-028 | Given evidence capture configured for 20s (10+10), when a clip is captured, then the resulting file duration is approximately 20 seconds | Integration test |
| AC-029 | Given face anonymization is enabled, when evidence is stored, then all faces in snapshots and clips are blurred | Visual verification test |

### AC-8: Alert Management

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-030 | Given a new incident, when it is created, then a WebSocket alert message is delivered to all connected clients within 1 second | Timing test with WebSocket client |
| AC-031 | Given a connected dashboard, when an alert arrives, then it appears in the alert panel with correct severity color | E2E test |
| AC-032 | Given an unacknowledged alert, when an operator clicks "Acknowledge", then the alert status updates and the unacknowledged count decreases | E2E test |

### AC-9: Dashboard

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-033 | Given an active camera stream, when the dashboard loads, then live video with detection overlays is displayed via WebSocket | E2E test |
| AC-034 | Given the analytics page, when daily view is selected, then detection counts for the past 7 days are displayed as a chart | E2E test |
| AC-035 | Given incident data, when CSV export is triggered, then a valid CSV file is downloaded containing all filtered incident records | Functional test |

### AC-10: Authentication & Authorization

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-036 | Given valid credentials, when login is attempted, then a JWT access token and refresh token are returned | API test |
| AC-037 | Given invalid credentials, when login is attempted, then a 401 response is returned with no token | API test |
| AC-038 | Given a Viewer role user, when they attempt to acknowledge an alert, then a 403 response is returned | API test |
| AC-039 | Given an expired access token, when an API call is made, then a 401 response is returned | API test |
| AC-040 | Given 6 failed login attempts in 1 minute, when the 6th attempt is made, then a 429 response is returned | API test |

### AC-11: Privacy

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-041 | Given face anonymization enabled, when an evidence snapshot is stored, then no recognizable face features remain (blur σ≥15) | Image analysis test |
| AC-042 | Given retention period of 90 days, when evidence is older than 90 days, then it is automatically deleted by the cleanup job | Scheduled task test |
| AC-043 | Given the live feed WebSocket, when frames are streamed to operators, then faces are NOT anonymized | Visual verification |

### AC-12: Deployment

| ID | Criteria | Verification Method |
|----|----------|-------------------|
| AC-044 | Given a machine with Docker Compose installed, when `docker-compose up` is run, then all services start successfully within 60 seconds | Deployment test |
| AC-045 | Given the deployed system, when the /health endpoint is called, then it returns 200 OK with service status | Smoke test |
| AC-046 | Given environment variables configured in .env, when containers start, then they use the configured values (not defaults) | Configuration test |

---

## 13. Requirements Traceability Structure

### 13.1 Traceability Matrix Template

The following structure shall be used to trace each requirement through design, implementation, and testing:

| Req ID | Requirement Summary | Design Component | Implementation Module | Test Case ID | Test Type | Status |
|--------|-------------------|-----------------|----------------------|--------------|-----------|--------|
| FR-001 | USB webcam input | Stream Manager | `app/detection/pipeline.py` | TC-001 | Integration | Pending |
| FR-008 | Weapon detection (YOLO) | Detection Pipeline | `app/detection/detector.py` | TC-007, TC-008 | Unit + Integration | Pending |
| FR-018 | Multi-frame verification | Verification Engine | `app/detection/verifier.py` | TC-015, TC-016 | Unit | Pending |
| FR-022 | Threat scoring | Scoring Engine | `app/detection/scorer.py` | TC-018, TC-019 | Unit | Pending |
| FR-027 | Auto incident creation | Incident Service | `app/services/incident_service.py` | TC-022 | Integration | Pending |
| FR-044 | Real-time alerts | Alert Service + WebSocket | `app/services/alert_service.py` | TC-030 | Integration | Pending |
| FR-061 | API authentication | Auth Middleware | `app/core/security.py` | TC-036, TC-037 | API | Pending |
| SEC-001 | Password hashing (bcrypt) | Auth Service | `app/services/auth_service.py` | TC-SEC-001 | Unit | Pending |
| PRV-001 | Face anonymization | Privacy Service | `app/detection/privacy.py` | TC-041 | Integration | Pending |
| AI-004 | mAP ≥ 0.60 | Detection Model | `app/detection/models/` | TC-AI-004 | Evaluation | Pending |
| NFR-001 | ≥15 FPS on GPU | Pipeline Architecture | `app/detection/pipeline.py` | TC-NFR-001 | Performance | Pending |

### 13.2 Traceability Coverage Rules

1. **Every functional requirement (FR-xxx)** shall map to at least one implementation module and one test case
2. **Every security requirement (SEC-xxx)** shall map to at least one security test case
3. **Every AI requirement (AI-xxx)** shall map to at least one evaluation metric or test
4. **Every non-functional requirement (NFR-xxx)** shall map to a measurable verification method
5. **Every acceptance criterion (AC-xxx)** shall reference the requirement(s) it validates

### 13.3 Requirement-to-Acceptance Criteria Mapping

| Requirement Group | Requirements | Acceptance Criteria |
|-------------------|-------------|-------------------|
| Video Input | FR-001 to FR-007 | AC-001 to AC-006 |
| AI Detection | FR-008 to FR-013 | AC-007 to AC-011 |
| Object Tracking | FR-014 to FR-017 | AC-012 to AC-014 |
| Multi-Frame Verification | FR-018 to FR-021 | AC-015 to AC-017 |
| Threat Scoring | FR-022 to FR-026 | AC-018 to AC-021 |
| Incident Management | FR-027 to FR-033 | AC-022 to AC-025 |
| Evidence Capture | FR-034 to FR-038 | AC-026 to AC-029 |
| Alert Management | FR-044 to FR-049 | AC-030 to AC-032 |
| Dashboard | FR-050 to FR-060 | AC-033 to AC-035 |
| Auth & Access | FR-061 to FR-068 | AC-036 to AC-040 |
| Privacy | PRV-001 to PRV-010 | AC-041 to AC-043 |
| Deployment | NFR-022 to NFR-024 | AC-044 to AC-046 |

### 13.4 Requirement Status Tracking

Each requirement shall be tracked through the following lifecycle:

```
Draft → Approved → Designed → Implemented → Tested → Verified
```

| Status | Definition |
|--------|-----------|
| Draft | Requirement captured but not yet reviewed |
| Approved | Requirement reviewed and accepted by stakeholders |
| Designed | Architecture/design documents reference this requirement |
| Implemented | Code implementing this requirement has been written |
| Tested | Test case(s) covering this requirement have been executed |
| Verified | Requirement confirmed as met via acceptance criteria |

---

## Document Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Author | | | |
| Reviewer | | | |
| Approver | | | |

---

*End of Software Requirements Specification*
