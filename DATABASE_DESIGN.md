# Database Design Document

## AI-Based Real-Time Threat Detection and Emergency Response Platform

| Document Info | |
|---|---|
| **Version** | 1.0 |
| **Date** | August 17, 2026 |
| **DBMS** | PostgreSQL 15 |
| **References** | SRS_DOCUMENT.md, TECHNICAL_ARCHITECTURE.md |

---

## Table of Contents

1. [Database Overview](#1-database-overview)
2. [Table Definitions](#2-table-definitions)
3. [ER Diagram Description](#3-er-diagram-description)
4. [Database Normalization Considerations](#4-database-normalization-considerations)
5. [Indexing Strategy](#5-indexing-strategy)
6. [Retention Considerations](#6-retention-considerations)
7. [Sample Records](#7-sample-records)

---

## 1. Database Overview

### 1.1 Schema Summary

| # | Table | Purpose | Expected Volume |
|---|-------|---------|-----------------|
| 1 | roles | Role definitions (RBAC) | 3-5 rows (static) |
| 2 | users | System users/operators | 10-50 rows |
| 3 | camera_locations | Physical locations of cameras | 5-20 rows |
| 4 | cameras | Camera devices and stream config | 4-8 rows |
| 5 | model_versions | AI model tracking | 5-20 rows |
| 6 | detections | Raw detection events from AI | 100K-1M+ rows/month |
| 7 | tracked_objects | Persistent tracked objects across frames | 10K-100K rows/month |
| 8 | incidents | Confirmed threat incidents | 50-500 rows/month |
| 9 | evidence | Snapshots and video clips | 100-1000 rows/month |
| 10 | alerts | Real-time alert records | 50-500 rows/month |
| 11 | notification_logs | Alert delivery tracking | 200-2000 rows/month |
| 12 | audit_logs | User action audit trail | 1K-10K rows/month |

### 1.2 Naming Conventions

| Convention | Rule | Example |
|-----------|------|---------|
| Tables | lowercase, plural, snake_case | `tracked_objects` |
| Columns | lowercase, snake_case | `risk_score` |
| Primary keys | `id` (UUID) or `id` (BIGSERIAL for high-volume) | `id UUID` |
| Foreign keys | `{referenced_table_singular}_id` | `camera_id` |
| Indexes | `idx_{table}_{column(s)}` | `idx_detections_camera_timestamp` |
| Unique constraints | `uq_{table}_{column(s)}` | `uq_users_email` |
| Check constraints | `chk_{table}_{column}` | `chk_incidents_severity` |
| Timestamps | `*_at` suffix, always TIMESTAMPTZ | `created_at` |

---

## 2. Table Definitions

---

### 2.1 `roles`

**Purpose**: Define system roles for RBAC. Static lookup table.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | SMALLSERIAL | NOT NULL | auto | PK | Role identifier |
| name | VARCHAR(30) | NOT NULL | — | UNIQUE (`uq_roles_name`) | Role name |
| description | VARCHAR(255) | NULL | — | — | Human-readable description |
| permissions | JSONB | NOT NULL | '{}' | — | Permission map |
| is_system | BOOLEAN | NOT NULL | true | — | Whether role is system-defined (non-deletable) |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Creation timestamp |

**Primary Key**: `id`
**Unique Constraints**: `uq_roles_name` ON (name)
**Indexes**: None needed (tiny table, always full-scanned)
**Relationships**: Referenced by `users.role_id`

---

### 2.2 `users`

**Purpose**: Store authenticated system users (admins, operators, viewers).

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | User identifier |
| email | VARCHAR(255) | NOT NULL | — | UNIQUE (`uq_users_email`) | Login email |
| password_hash | VARCHAR(255) | NOT NULL | — | — | bcrypt hash (60 chars) |
| full_name | VARCHAR(150) | NOT NULL | — | — | Display name |
| role_id | SMALLINT | NOT NULL | — | FK → roles.id | Assigned role |
| is_active | BOOLEAN | NOT NULL | true | — | Account active flag |
| last_login_at | TIMESTAMPTZ | NULL | — | — | Last successful login |
| failed_login_count | INTEGER | NOT NULL | 0 | CHECK (≥ 0) | Consecutive failed logins |
| locked_until | TIMESTAMPTZ | NULL | — | — | Account lockout expiry |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Registration time |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Last profile update |

**Primary Key**: `id`
**Foreign Keys**: `role_id` → `roles(id)` ON DELETE RESTRICT
**Unique Constraints**: `uq_users_email` ON (email)
**Indexes**:
- `idx_users_email` ON (email) — login lookups
- `idx_users_role_id` ON (role_id) — role-based queries
**Check Constraints**:
- `chk_users_email_format` CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
**Relationships**: One user → many audit_logs, many notification_logs, many alerts (acknowledged_by)

---

### 2.3 `camera_locations`

**Purpose**: Define physical locations where cameras are installed. Allows grouping cameras by area.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Location identifier |
| name | VARCHAR(100) | NOT NULL | — | UNIQUE (`uq_camera_locations_name`) | Location name |
| building | VARCHAR(100) | NULL | — | — | Building name |
| floor | VARCHAR(20) | NULL | — | — | Floor/level |
| zone | VARCHAR(50) | NULL | — | — | Zone or section |
| description | TEXT | NULL | — | — | Detailed description |
| coordinates | JSONB | NULL | — | — | {lat, lng} if available |
| is_active | BOOLEAN | NOT NULL | true | — | Whether location is operational |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Last update |

**Primary Key**: `id`
**Unique Constraints**: `uq_camera_locations_name` ON (name)
**Indexes**:
- `idx_camera_locations_building` ON (building) — filter by building
**Relationships**: One location → many cameras

---

### 2.4 `cameras`

**Purpose**: Register camera devices with stream configuration and operational metadata.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Camera identifier |
| name | VARCHAR(100) | NOT NULL | — | — | Display name |
| location_id | UUID | NULL | — | FK → camera_locations.id | Physical location |
| stream_url | VARCHAR(500) | NOT NULL | — | — | RTSP/HTTP/device path |
| stream_type | VARCHAR(20) | NOT NULL | 'rtsp' | CHECK IN ('rtsp','http','usb','file') | Input type |
| resolution_width | INTEGER | NULL | — | CHECK (> 0) | Native resolution width |
| resolution_height | INTEGER | NULL | — | CHECK (> 0) | Native resolution height |
| target_fps | INTEGER | NOT NULL | 15 | CHECK (1-60) | Target capture FPS |
| status | VARCHAR(20) | NOT NULL | 'offline' | CHECK IN ('online','offline','processing','error','maintenance') | Current state |
| is_enabled | BOOLEAN | NOT NULL | true | — | Whether camera should auto-start |
| last_online_at | TIMESTAMPTZ | NULL | — | — | Last successful frame received |
| error_message | VARCHAR(500) | NULL | — | — | Last error if status='error' |
| metadata | JSONB | NOT NULL | '{}' | — | Flexible metadata (brand, model, angle, etc.) |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Registration time |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Last config update |

**Primary Key**: `id`
**Foreign Keys**: `location_id` → `camera_locations(id)` ON DELETE SET NULL
**Indexes**:
- `idx_cameras_location_id` ON (location_id)
- `idx_cameras_status` ON (status)
- `idx_cameras_is_enabled` ON (is_enabled) WHERE is_enabled = true
**Check Constraints**:
- `chk_cameras_stream_type` CHECK (stream_type IN ('rtsp','http','usb','file'))
- `chk_cameras_status` CHECK (status IN ('online','offline','processing','error','maintenance'))
- `chk_cameras_target_fps` CHECK (target_fps BETWEEN 1 AND 60)
**Relationships**: One camera → many detections, many incidents, many tracked_objects

---

### 2.5 `model_versions`

**Purpose**: Track AI/ML model deployments, enabling reproducibility and rollback.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Model version identifier |
| model_name | VARCHAR(100) | NOT NULL | — | — | Model family name (e.g., "weapon-detector") |
| version | VARCHAR(50) | NOT NULL | — | — | Version string (e.g., "1.2.0") |
| architecture | VARCHAR(50) | NOT NULL | — | — | YOLO variant (yolov8m, yolov9c, etc.) |
| file_path | VARCHAR(500) | NOT NULL | — | — | Path to weights file |
| file_hash_sha256 | VARCHAR(64) | NOT NULL | — | — | SHA-256 of weights file |
| input_size | INTEGER | NOT NULL | 640 | — | Model input resolution |
| classes | JSONB | NOT NULL | — | — | Array of class names |
| num_classes | INTEGER | NOT NULL | — | CHECK (> 0) | Number of detection classes |
| training_dataset | VARCHAR(255) | NULL | — | — | Dataset description |
| training_epochs | INTEGER | NULL | — | — | Training epochs |
| map_score | FLOAT | NULL | — | CHECK (0-1) | Evaluation mAP@0.5 |
| is_active | BOOLEAN | NOT NULL | false | — | Currently deployed model |
| deployed_at | TIMESTAMPTZ | NULL | — | — | When model was activated |
| deployed_by | UUID | NULL | — | FK → users.id | Who deployed it |
| notes | TEXT | NULL | — | — | Release notes |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Record creation time |

**Primary Key**: `id`
**Foreign Keys**: `deployed_by` → `users(id)` ON DELETE SET NULL
**Unique Constraints**: `uq_model_versions_name_version` ON (model_name, version)
**Indexes**:
- `idx_model_versions_active` ON (is_active) WHERE is_active = true
- `idx_model_versions_name` ON (model_name)
**Check Constraints**:
- `chk_model_versions_map` CHECK (map_score IS NULL OR (map_score >= 0 AND map_score <= 1))
**Relationships**: Referenced by `detections.model_version_id`

---

### 2.6 `detections`

**Purpose**: Store every raw detection event from the AI pipeline. High-volume table — primary source for analytics.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | BIGSERIAL | NOT NULL | auto | PK | Detection identifier |
| camera_id | UUID | NOT NULL | — | FK → cameras.id | Source camera |
| model_version_id | UUID | NULL | — | FK → model_versions.id | Model that produced detection |
| timestamp | TIMESTAMPTZ | NOT NULL | — | — | Frame timestamp |
| frame_number | BIGINT | NOT NULL | — | — | Sequential frame number |
| class_label | VARCHAR(30) | NOT NULL | — | — | Detected class (handgun/rifle/knife/person) |
| confidence | REAL | NOT NULL | — | CHECK (0-1) | Detection confidence |
| bbox_x1 | REAL | NOT NULL | — | — | Bounding box top-left X (normalized 0-1) |
| bbox_y1 | REAL | NOT NULL | — | — | Bounding box top-left Y (normalized 0-1) |
| bbox_x2 | REAL | NOT NULL | — | — | Bounding box bottom-right X (normalized 0-1) |
| bbox_y2 | REAL | NOT NULL | — | — | Bounding box bottom-right Y (normalized 0-1) |
| track_id | INTEGER | NULL | — | — | Assigned tracker ID (NULL if untracked) |
| is_weapon | BOOLEAN | NOT NULL | false | — | Whether class is a weapon type |
| is_verified | BOOLEAN | NOT NULL | false | — | Passed multi-frame verification |
| processing_time_ms | REAL | NULL | — | — | Inference time for this detection |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Record insert time |

**Primary Key**: `id`
**Foreign Keys**:
- `camera_id` → `cameras(id)` ON DELETE CASCADE
- `model_version_id` → `model_versions(id)` ON DELETE SET NULL
**Indexes**:
- `idx_detections_camera_timestamp` ON (camera_id, timestamp DESC) — primary query pattern
- `idx_detections_timestamp` ON (timestamp DESC) — time-range queries
- `idx_detections_class_label` ON (class_label) — filter by class
- `idx_detections_is_verified` ON (camera_id, timestamp DESC) WHERE is_verified = true — verified only
- `idx_detections_track_id` ON (camera_id, track_id) WHERE track_id IS NOT NULL — track lookups
**Check Constraints**:
- `chk_detections_confidence` CHECK (confidence >= 0 AND confidence <= 1)
- `chk_detections_bbox` CHECK (bbox_x1 >= 0 AND bbox_x2 <= 1 AND bbox_y1 >= 0 AND bbox_y2 <= 1 AND bbox_x2 > bbox_x1 AND bbox_y2 > bbox_y1)
**Partitioning**: Range partition on `timestamp` (monthly partitions recommended)
**Relationships**: Many detections → one camera, many detections → one incident (via incident_detections)

---

### 2.7 `tracked_objects`

**Purpose**: Store the lifecycle of tracked objects across frames — each row represents a complete track from first appearance to disappearance.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | BIGSERIAL | NOT NULL | auto | PK | Track record identifier |
| camera_id | UUID | NOT NULL | — | FK → cameras.id | Source camera |
| track_id | INTEGER | NOT NULL | — | — | Pipeline-assigned track ID |
| class_label | VARCHAR(30) | NOT NULL | — | — | Dominant detected class |
| first_seen_at | TIMESTAMPTZ | NOT NULL | — | — | First frame timestamp |
| last_seen_at | TIMESTAMPTZ | NOT NULL | — | — | Last frame timestamp |
| duration_seconds | REAL | NOT NULL | — | CHECK (≥ 0) | Total tracking duration |
| total_frames | INTEGER | NOT NULL | — | CHECK (> 0) | Frames where object appeared |
| avg_confidence | REAL | NOT NULL | — | CHECK (0-1) | Mean confidence across frames |
| min_confidence | REAL | NOT NULL | — | CHECK (0-1) | Lowest confidence in track |
| max_confidence | REAL | NOT NULL | — | CHECK (0-1) | Highest confidence in track |
| last_bbox_x1 | REAL | NOT NULL | — | — | Last known position |
| last_bbox_y1 | REAL | NOT NULL | — | — | Last known position |
| last_bbox_x2 | REAL | NOT NULL | — | — | Last known position |
| last_bbox_y2 | REAL | NOT NULL | — | — | Last known position |
| is_weapon_track | BOOLEAN | NOT NULL | false | — | Whether track is for a weapon class |
| is_verified | BOOLEAN | NOT NULL | false | — | Passed multi-frame verification |
| verification_frame_count | INTEGER | NOT NULL | 0 | — | Frames that contributed to verification (N value) |
| risk_score | REAL | NULL | — | CHECK (0-1 or NULL) | Computed threat score (NULL if not scored) |
| incident_id | UUID | NULL | — | FK → incidents.id | Linked incident (if threat confirmed) |
| status | VARCHAR(20) | NOT NULL | 'active' | CHECK IN ('active','lost','completed') | Track lifecycle state |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Record creation |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Last update |

**Primary Key**: `id`
**Foreign Keys**:
- `camera_id` → `cameras(id)` ON DELETE CASCADE
- `incident_id` → `incidents(id)` ON DELETE SET NULL
**Unique Constraints**: `uq_tracked_objects_camera_track` ON (camera_id, track_id, first_seen_at) — prevent duplicate track entries
**Indexes**:
- `idx_tracked_objects_camera_time` ON (camera_id, first_seen_at DESC)
- `idx_tracked_objects_incident` ON (incident_id) WHERE incident_id IS NOT NULL
- `idx_tracked_objects_verified_weapons` ON (camera_id, is_verified) WHERE is_weapon_track = true AND is_verified = true
- `idx_tracked_objects_status` ON (status) WHERE status = 'active'
**Check Constraints**:
- `chk_tracked_objects_status` CHECK (status IN ('active','lost','completed'))
- `chk_tracked_objects_duration` CHECK (duration_seconds >= 0)
- `chk_tracked_objects_confidence` CHECK (avg_confidence >= 0 AND avg_confidence <= 1)
**Relationships**: Many tracked_objects → one camera, one tracked_object → zero or one incident

---

### 2.8 `incidents`

**Purpose**: Confirmed threat events requiring human attention. Core entity for incident management lifecycle.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Incident identifier |
| camera_id | UUID | NOT NULL | — | FK → cameras.id | Source camera |
| incident_number | SERIAL | NOT NULL | auto | UNIQUE | Human-readable sequential number |
| title | VARCHAR(255) | NOT NULL | — | — | Auto-generated or manual title |
| description | TEXT | NULL | — | — | Detailed description |
| severity | VARCHAR(10) | NOT NULL | — | CHECK IN ('low','medium','high','critical') | Threat severity |
| status | VARCHAR(15) | NOT NULL | 'open' | CHECK IN ('open','acknowledged','investigating','resolved','closed','false_positive') | Incident lifecycle |
| risk_score | REAL | NOT NULL | — | CHECK (0-1) | Computed threat score |
| weapon_class | VARCHAR(30) | NULL | — | — | Primary weapon detected |
| weapon_count | INTEGER | NOT NULL | 1 | CHECK (≥ 1) | Number of weapons detected |
| person_count | INTEGER | NULL | — | CHECK (≥ 0) | Persons in frame at detection |
| detection_confidence | REAL | NOT NULL | — | CHECK (0-1) | Average detection confidence |
| started_at | TIMESTAMPTZ | NOT NULL | — | — | First detection timestamp |
| acknowledged_at | TIMESTAMPTZ | NULL | — | — | When operator acknowledged |
| acknowledged_by | UUID | NULL | — | FK → users.id | Who acknowledged |
| resolved_at | TIMESTAMPTZ | NULL | — | — | When marked resolved |
| resolved_by | UUID | NULL | — | FK → users.id | Who resolved |
| closed_at | TIMESTAMPTZ | NULL | — | — | When closed |
| closed_by | UUID | NULL | — | FK → users.id | Who closed |
| resolution_notes | TEXT | NULL | — | — | Notes added at resolution |
| is_false_positive | BOOLEAN | NOT NULL | false | — | Marked as false positive |
| version | INTEGER | NOT NULL | 1 | — | Optimistic locking version |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Record creation |
| updated_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Last modification |

**Primary Key**: `id`
**Foreign Keys**:
- `camera_id` → `cameras(id)` ON DELETE RESTRICT
- `acknowledged_by` → `users(id)` ON DELETE SET NULL
- `resolved_by` → `users(id)` ON DELETE SET NULL
- `closed_by` → `users(id)` ON DELETE SET NULL
**Unique Constraints**: `uq_incidents_number` ON (incident_number)
**Indexes**:
- `idx_incidents_status` ON (status) — filter by lifecycle state
- `idx_incidents_severity` ON (severity) — filter by severity
- `idx_incidents_camera_id` ON (camera_id) — per-camera queries
- `idx_incidents_started_at` ON (started_at DESC) — chronological listing
- `idx_incidents_open` ON (status, severity) WHERE status IN ('open','acknowledged','investigating') — active incidents
**Check Constraints**:
- `chk_incidents_severity` CHECK (severity IN ('low','medium','high','critical'))
- `chk_incidents_status` CHECK (status IN ('open','acknowledged','investigating','resolved','closed','false_positive'))
- `chk_incidents_risk_score` CHECK (risk_score >= 0 AND risk_score <= 1)
- `chk_incidents_weapon_count` CHECK (weapon_count >= 1)
**Relationships**: One incident → many evidence, many alerts, many tracked_objects, many detections (via junction)

---

### 2.9 `incident_detections` (Junction Table)

**Purpose**: Link incidents to their contributing raw detections (many-to-many).

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | BIGSERIAL | NOT NULL | auto | PK | Record identifier |
| incident_id | UUID | NOT NULL | — | FK → incidents.id | Parent incident |
| detection_id | BIGINT | NOT NULL | — | FK → detections.id | Contributing detection |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Link creation time |

**Primary Key**: `id`
**Foreign Keys**:
- `incident_id` → `incidents(id)` ON DELETE CASCADE
- `detection_id` → `detections(id)` ON DELETE CASCADE
**Unique Constraints**: `uq_incident_detections` ON (incident_id, detection_id)
**Indexes**:
- `idx_incident_detections_incident` ON (incident_id)
- `idx_incident_detections_detection` ON (detection_id)

---

### 2.10 `evidence`

**Purpose**: Store metadata for captured evidence files (snapshots and video clips) linked to incidents.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Evidence identifier |
| incident_id | UUID | NOT NULL | — | FK → incidents.id | Parent incident |
| camera_id | UUID | NOT NULL | — | FK → cameras.id | Source camera |
| type | VARCHAR(10) | NOT NULL | — | CHECK IN ('snapshot','clip') | Evidence media type |
| file_path | VARCHAR(500) | NOT NULL | — | — | Relative path from evidence root |
| file_name | VARCHAR(255) | NOT NULL | — | — | Original filename |
| file_size_bytes | BIGINT | NOT NULL | — | CHECK (> 0) | File size in bytes |
| mime_type | VARCHAR(50) | NOT NULL | — | — | MIME type (image/jpeg, video/mp4) |
| duration_seconds | REAL | NULL | — | CHECK (> 0 or NULL) | Video duration (clips only) |
| resolution_width | INTEGER | NULL | — | — | Frame width in pixels |
| resolution_height | INTEGER | NULL | — | — | Frame height in pixels |
| is_anonymized | BOOLEAN | NOT NULL | false | — | Whether face anonymization applied |
| anonymization_failed | BOOLEAN | NOT NULL | false | — | Whether anonymization was attempted but failed |
| frame_number | BIGINT | NULL | — | — | Frame number at capture (snapshots) |
| annotations | JSONB | NULL | — | — | Bounding boxes drawn on evidence |
| captured_at | TIMESTAMPTZ | NOT NULL | — | — | When evidence was captured |
| expires_at | TIMESTAMPTZ | NULL | — | — | Scheduled deletion date |
| metadata | JSONB | NOT NULL | '{}' | — | Additional metadata |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Record creation |

**Primary Key**: `id`
**Foreign Keys**:
- `incident_id` → `incidents(id)` ON DELETE CASCADE
- `camera_id` → `cameras(id)` ON DELETE RESTRICT
**Indexes**:
- `idx_evidence_incident_id` ON (incident_id) — get evidence for incident
- `idx_evidence_expires_at` ON (expires_at) WHERE expires_at IS NOT NULL — retention cleanup
- `idx_evidence_type` ON (type) — filter by snapshot/clip
- `idx_evidence_captured_at` ON (captured_at DESC) — chronological
**Check Constraints**:
- `chk_evidence_type` CHECK (type IN ('snapshot','clip'))
- `chk_evidence_file_size` CHECK (file_size_bytes > 0)
- `chk_evidence_duration` CHECK (duration_seconds IS NULL OR duration_seconds > 0)
**Relationships**: Many evidence → one incident, many evidence → one camera

---

### 2.11 `alerts`

**Purpose**: Real-time alert records generated when incidents are created or escalated.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | UUID | NOT NULL | gen_random_uuid() | PK | Alert identifier |
| incident_id | UUID | NOT NULL | — | FK → incidents.id | Related incident |
| camera_id | UUID | NOT NULL | — | FK → cameras.id | Source camera |
| severity | VARCHAR(10) | NOT NULL | — | CHECK IN ('low','medium','high','critical') | Alert severity |
| title | VARCHAR(255) | NOT NULL | — | — | Short alert title |
| message | TEXT | NOT NULL | — | — | Detailed alert message |
| alert_type | VARCHAR(30) | NOT NULL | 'threat_detected' | — | Type categorization |
| is_read | BOOLEAN | NOT NULL | false | — | Whether viewed in dashboard |
| is_acknowledged | BOOLEAN | NOT NULL | false | — | Whether explicitly acknowledged |
| acknowledged_by | UUID | NULL | — | FK → users.id | Who acknowledged |
| acknowledged_at | TIMESTAMPTZ | NULL | — | — | Acknowledgement time |
| is_dismissed | BOOLEAN | NOT NULL | false | — | Whether dismissed without action |
| dismissed_by | UUID | NULL | — | FK → users.id | Who dismissed |
| dismissed_at | TIMESTAMPTZ | NULL | — | — | Dismissal time |
| priority_order | INTEGER | NOT NULL | 0 | — | Display ordering (higher = more important) |
| expires_at | TIMESTAMPTZ | NULL | — | — | Auto-dismiss after this time |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Alert creation time |

**Primary Key**: `id`
**Foreign Keys**:
- `incident_id` → `incidents(id)` ON DELETE CASCADE
- `camera_id` → `cameras(id)` ON DELETE CASCADE
- `acknowledged_by` → `users(id)` ON DELETE SET NULL
- `dismissed_by` → `users(id)` ON DELETE SET NULL
**Indexes**:
- `idx_alerts_incident_id` ON (incident_id)
- `idx_alerts_unacknowledged` ON (created_at DESC) WHERE is_acknowledged = false — dashboard query
- `idx_alerts_severity_time` ON (severity, created_at DESC) — severity-filtered lists
- `idx_alerts_camera_id` ON (camera_id) — per-camera alerts
**Check Constraints**:
- `chk_alerts_severity` CHECK (severity IN ('low','medium','high','critical'))
**Relationships**: Many alerts → one incident, many alerts → one camera

---

### 2.12 `notification_logs`

**Purpose**: Track delivery status of alert notifications through various channels (WebSocket, future: email/SMS).

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | BIGSERIAL | NOT NULL | auto | PK | Log entry identifier |
| alert_id | UUID | NOT NULL | — | FK → alerts.id | Source alert |
| user_id | UUID | NULL | — | FK → users.id | Target recipient (NULL for broadcast) |
| channel | VARCHAR(30) | NOT NULL | — | CHECK IN ('websocket','email','sms','push') | Delivery channel |
| status | VARCHAR(20) | NOT NULL | 'pending' | CHECK IN ('pending','sent','delivered','failed','expired') | Delivery status |
| sent_at | TIMESTAMPTZ | NULL | — | — | When notification was sent |
| delivered_at | TIMESTAMPTZ | NULL | — | — | When delivery confirmed |
| failed_at | TIMESTAMPTZ | NULL | — | — | When delivery failed |
| failure_reason | VARCHAR(500) | NULL | — | — | Error message on failure |
| retry_count | INTEGER | NOT NULL | 0 | CHECK (≥ 0) | Number of delivery attempts |
| max_retries | INTEGER | NOT NULL | 3 | — | Maximum retry attempts |
| metadata | JSONB | NOT NULL | '{}' | — | Channel-specific details |
| created_at | TIMESTAMPTZ | NOT NULL | NOW() | — | Record creation |

**Primary Key**: `id`
**Foreign Keys**:
- `alert_id` → `alerts(id)` ON DELETE CASCADE
- `user_id` → `users(id)` ON DELETE SET NULL
**Indexes**:
- `idx_notification_logs_alert_id` ON (alert_id)
- `idx_notification_logs_user_status` ON (user_id, status) — user notification history
- `idx_notification_logs_pending` ON (status, created_at) WHERE status IN ('pending','failed') — retry queue
**Check Constraints**:
- `chk_notification_logs_channel` CHECK (channel IN ('websocket','email','sms','push'))
- `chk_notification_logs_status` CHECK (status IN ('pending','sent','delivered','failed','expired'))
**Relationships**: Many notification_logs → one alert, many notification_logs → one user

---

### 2.13 `audit_logs`

**Purpose**: Immutable append-only record of all user actions and significant system events for compliance and accountability.

| Column | Data Type | Nullable | Default | Constraints | Description |
|--------|-----------|----------|---------|-------------|-------------|
| id | BIGSERIAL | NOT NULL | auto | PK | Log entry identifier |
| user_id | UUID | NULL | — | FK → users.id | Acting user (NULL for system) |
| action | VARCHAR(50) | NOT NULL | — | — | Action performed |
| resource_type | VARCHAR(50) | NOT NULL | — | — | Entity type affected |
| resource_id | VARCHAR(100) | NULL | — | — | Affected entity ID |
| description | TEXT | NULL | — | — | Human-readable description |
| changes | JSONB | NULL | — | — | Before/after state for updates |
| ip_address | INET | NULL | — | — | Client IP address |
| user_agent | VARCHAR(500) | NULL | — | — | Client user agent string |
| request_id | UUID | NULL | — | — | Correlation ID from request |
| session_id | VARCHAR(100) | NULL | — | — | Session identifier |
| severity | VARCHAR(10) | NOT NULL | 'info' | CHECK IN ('info','warning','critical') | Log severity |
| timestamp | TIMESTAMPTZ | NOT NULL | NOW() | — | Event timestamp |

**Primary Key**: `id`
**Foreign Keys**: `user_id` → `users(id)` ON DELETE SET NULL
**Indexes**:
- `idx_audit_logs_timestamp` ON (timestamp DESC) — chronological queries
- `idx_audit_logs_user_id` ON (user_id, timestamp DESC) — per-user history
- `idx_audit_logs_action` ON (action) — filter by action type
- `idx_audit_logs_resource` ON (resource_type, resource_id) — resource history
- `idx_audit_logs_severity` ON (severity) WHERE severity != 'info' — warning/critical only
**Check Constraints**:
- `chk_audit_logs_severity` CHECK (severity IN ('info','warning','critical'))
**Immutability**: This table should have no UPDATE or DELETE permissions granted to the application role. Enforced via PostgreSQL GRANT/REVOKE.
**Relationships**: Many audit_logs → one user (nullable)

### Audit Action Types

| Action | Resource Type | Description |
|--------|-------------|-------------|
| user.login | user | Successful login |
| user.login_failed | user | Failed login attempt |
| user.logout | user | User logged out |
| user.created | user | New user registered |
| user.updated | user | User profile modified |
| user.deactivated | user | User account disabled |
| incident.created | incident | New incident (auto or manual) |
| incident.status_changed | incident | Status transition |
| incident.false_positive | incident | Marked as false positive |
| alert.acknowledged | alert | Alert acknowledged |
| alert.dismissed | alert | Alert dismissed |
| camera.created | camera | Camera registered |
| camera.updated | camera | Camera config changed |
| camera.deleted | camera | Camera removed |
| camera.started | camera | Stream processing started |
| camera.stopped | camera | Stream processing stopped |
| config.updated | config | System config changed |
| model.deployed | model_version | AI model activated |
| evidence.deleted | evidence | Evidence manually purged |

---

## 3. ER Diagram Description

### 3.1 Relationships Summary

```
roles (1) ────────< (M) users
users (1) ────────< (M) audit_logs
users (1) ────────< (M) notification_logs
users (1) ────────< (M) incidents (acknowledged_by, resolved_by, closed_by)
users (1) ────────< (M) alerts (acknowledged_by, dismissed_by)
users (1) ────────< (M) model_versions (deployed_by)

camera_locations (1) ────────< (M) cameras

cameras (1) ────────< (M) detections
cameras (1) ────────< (M) tracked_objects
cameras (1) ────────< (M) incidents
cameras (1) ────────< (M) evidence
cameras (1) ────────< (M) alerts

model_versions (1) ────────< (M) detections

incidents (1) ────────< (M) evidence
incidents (1) ────────< (M) alerts
incidents (1) ────────< (M) tracked_objects
incidents (1) ────────< (M) incident_detections

detections (1) ────────< (M) incident_detections

alerts (1) ────────< (M) notification_logs
```

### 3.2 Cardinality Details

| Relationship | Type | Description |
|-------------|------|-------------|
| roles → users | 1:M | One role assigned to many users |
| camera_locations → cameras | 1:M | One location has many cameras |
| cameras → detections | 1:M | One camera produces millions of detections over time |
| cameras → tracked_objects | 1:M | One camera produces thousands of tracks |
| cameras → incidents | 1:M | One camera may have many incidents |
| model_versions → detections | 1:M | One model version produces many detections |
| incidents → evidence | 1:M | One incident has 1-5 evidence items typically |
| incidents → alerts | 1:M | One incident generates 1-3 alerts typically |
| incidents → tracked_objects | 1:M | One incident may involve multiple weapon tracks |
| incidents ↔ detections | M:M | Via incident_detections junction table |
| alerts → notification_logs | 1:M | One alert generates notifications per channel/user |
| users → audit_logs | 1:M | One user has many audit entries |

### 3.3 Entity Groups

```
┌─────────────────────────┐     ┌─────────────────────────────────────┐
│   IDENTITY & ACCESS     │     │          INFRASTRUCTURE              │
│                         │     │                                     │
│  ┌───────┐  ┌───────┐  │     │  ┌──────────────┐  ┌────────────┐  │
│  │ roles │←─│ users │  │     │  │camera_locations│←─│  cameras   │  │
│  └───────┘  └───┬───┘  │     │  └──────────────┘  └─────┬──────┘  │
│                 │       │     │                          │          │
└─────────────────┼───────┘     └──────────────────────────┼──────────┘
                  │                                        │
                  │              ┌──────────────────────────┼──────────┐
                  │              │      AI / DETECTION      │          │
                  │              │                          ▼          │
                  │              │  ┌──────────────┐  ┌──────────┐    │
                  │              │  │model_versions│→ │detections│    │
                  │              │  └──────────────┘  └────┬─────┘    │
                  │              │                         │           │
                  │              │  ┌───────────────────┐  │           │
                  │              │  │  tracked_objects  │←─┘           │
                  │              │  └─────────┬─────────┘              │
                  │              └────────────┼────────────────────────┘
                  │                           │
                  │              ┌────────────┼────────────────────────┐
                  │              │  INCIDENT MANAGEMENT  │              │
                  │              │            ▼          │              │
                  │              │  ┌──────────────┐    │              │
                  └──────────────┼─→│  incidents   │    │              │
                                │  └───┬──────┬───┘    │              │
                                │      │      │        │              │
                                │      ▼      ▼        │              │
                                │ ┌────────┐ ┌──────┐  │              │
                                │ │evidence│ │alerts│  │              │
                                │ └────────┘ └──┬───┘  │              │
                                │               │      │              │
                                │               ▼      │              │
                                │  ┌──────────────────┐│              │
                                │  │notification_logs ││              │
                                │  └──────────────────┘│              │
                                └──────────────────────────────────────┘

                  ┌──────────────────────────┐
                  │       AUDIT              │
                  │  ┌──────────────────┐    │
                  │  │   audit_logs     │    │
                  │  └──────────────────┘    │
                  └──────────────────────────┘
```

---

## 4. Database Normalization Considerations

### 4.1 Normal Form Assessment

| Table | Normal Form | Notes |
|-------|-------------|-------|
| roles | 3NF | Flat structure, no transitive dependencies |
| users | 3NF | All attributes depend on user ID only |
| camera_locations | 3NF | Location attributes grouped correctly |
| cameras | 3NF | Location separated into camera_locations |
| model_versions | 3NF | Self-contained model metadata |
| detections | 3NF | Atomic bbox values (not JSONB); each column depends only on PK |
| tracked_objects | 3NF | Aggregated track summary; denormalized for performance (see below) |
| incidents | 3NF | Status-related timestamps are dependent on status transitions |
| evidence | 3NF | File metadata all depends on evidence ID |
| alerts | 3NF | Alert details depend on alert ID |
| notification_logs | 3NF | Delivery tracking per notification |
| audit_logs | 3NF | Event data depends on log entry ID |

### 4.2 Intentional Denormalization

| Table | Denormalized Field | Reason |
|-------|-------------------|--------|
| `tracked_objects` | avg_confidence, min_confidence, max_confidence | Avoids expensive aggregate queries over millions of detection rows for each tracked object |
| `tracked_objects` | duration_seconds | Pre-computed from first_seen_at and last_seen_at to avoid timestamp arithmetic in queries |
| `incidents` | weapon_class, weapon_count, person_count, detection_confidence | Snapshot of state at incident creation; avoids joining to detections for listing queries |
| `alerts` | camera_id | Duplicates incident.camera_id for direct alert→camera queries without incident join |
| `evidence` | camera_id | Same reasoning as alerts.camera_id |
| `detections` | is_weapon | Derived from class_label; avoids IN ('handgun','rifle','knife') checks in hot queries |

### 4.3 JSONB Usage Justification

| Table.Column | Contents | Why JSONB over columns |
|-------------|----------|----------------------|
| roles.permissions | `{"can_view_feed": true, "can_manage_cameras": true, ...}` | Permissions evolve without migrations |
| cameras.metadata | `{"brand": "Hikvision", "model": "DS-2CD2143G2", "angle": 120}` | Vendor-specific; varies per camera |
| evidence.annotations | `[{"class": "handgun", "bbox": [...], "confidence": 0.87}]` | Variable number of annotations |
| evidence.metadata | `{"codec": "h264", "bitrate": 2000000}` | Media-specific attributes |
| audit_logs.changes | `{"before": {"status": "open"}, "after": {"status": "acknowledged"}}` | Arbitrary field changes |
| camera_locations.coordinates | `{"lat": 28.6139, "lng": 77.2090}` | Optional geolocation |
| notification_logs.metadata | `{"websocket_session_id": "abc123"}` | Channel-specific details |

### 4.4 Constraint Philosophy

- **Strict NOT NULL** on all critical business columns
- **CHECK constraints** for enums (not PostgreSQL ENUM type — easier to extend)
- **Foreign keys** enforce referential integrity
- **ON DELETE CASCADE** for child records that make no sense without parent (evidence, alerts, notification_logs)
- **ON DELETE RESTRICT** for important references that should prevent deletion (cameras referenced by incidents)
- **ON DELETE SET NULL** for optional references (user references in audit logs)

---

## 5. Indexing Strategy

### 5.1 Index Design Principles

| Principle | Application |
|-----------|-------------|
| Index for query patterns, not tables | Every index maps to a specific query in the application |
| Partial indexes for filtered queries | WHERE clauses on common filters (is_active, status, is_verified) |
| Composite indexes ordered by selectivity | Most selective column first (camera_id before timestamp) |
| Covering indexes where appropriate | Include frequently accessed columns to avoid table lookup |
| Avoid over-indexing | Each index costs write performance and storage |

### 5.2 Critical Query Patterns → Index Mapping

| Query Pattern | Index | Expected Usage |
|---------------|-------|----------------|
| Get recent detections for camera | `idx_detections_camera_timestamp` (camera_id, timestamp DESC) | Detection pipeline writes + analytics |
| List active/open incidents | `idx_incidents_open` (status, severity) WHERE status IN (...) | Dashboard polling |
| Get unacknowledged alerts | `idx_alerts_unacknowledged` (created_at DESC) WHERE is_acknowledged = false | Alert panel |
| Get evidence for incident | `idx_evidence_incident_id` (incident_id) | Incident detail view |
| Find expired evidence | `idx_evidence_expires_at` (expires_at) WHERE expires_at IS NOT NULL | Cleanup job |
| User login lookup | `idx_users_email` (email) | Authentication |
| Audit history by user | `idx_audit_logs_user_id` (user_id, timestamp DESC) | Admin panel |
| Active weapon tracks | `idx_tracked_objects_verified_weapons` WHERE is_weapon_track AND is_verified | Pipeline queries |
| Detection analytics by time | `idx_detections_timestamp` (timestamp DESC) | Analytics charts |
| Pending notifications for retry | `idx_notification_logs_pending` WHERE status IN ('pending','failed') | Notification worker |

### 5.3 Index Storage Estimate

| Table | Rows (1 year) | Table Size | Total Index Size |
|-------|--------------|-----------|-----------------|
| detections | ~10M | ~2 GB | ~1.5 GB |
| tracked_objects | ~500K | ~200 MB | ~150 MB |
| incidents | ~5K | ~10 MB | ~5 MB |
| evidence | ~10K | ~5 MB | ~3 MB |
| alerts | ~5K | ~3 MB | ~2 MB |
| audit_logs | ~100K | ~50 MB | ~30 MB |
| notification_logs | ~20K | ~10 MB | ~5 MB |
| **Total** | | **~2.3 GB** | **~1.7 GB** |

### 5.4 Index Maintenance

| Action | Frequency | Purpose |
|--------|-----------|---------|
| REINDEX | Monthly | Rebuild bloated indexes |
| VACUUM ANALYZE | Daily (auto) | Update statistics, reclaim space |
| pg_stat_user_indexes | Weekly review | Identify unused indexes |
| Index usage check | Monthly | Remove indexes with 0 scans |

---

## 6. Retention Considerations

### 6.1 Data Lifecycle Policies

| Table | Retention Period | Archival Strategy | Deletion Method |
|-------|-----------------|-------------------|-----------------|
| detections | 90 days (hot) + 365 days (cold) | Partition drop for old months; optional export to CSV before drop | DROP PARTITION |
| tracked_objects | 180 days | DELETE with batch (1000 rows/transaction) | Batch DELETE |
| incidents | Permanent (or 5 years) | Never auto-deleted; manual archival | N/A |
| evidence (files) | 90 days (configurable) | Delete files; keep DB record with `file_deleted=true` | File unlink + DB update |
| evidence (metadata) | 365 days | Keep longer than files for audit purposes | Batch DELETE |
| alerts | 365 days | DELETE old acknowledged/dismissed alerts | Batch DELETE |
| notification_logs | 90 days | Bulk DELETE for completed deliveries | Batch DELETE |
| audit_logs | Permanent (or 7 years) | Never auto-deleted; regulatory compliance | N/A |
| model_versions | Permanent | Keep all for reproducibility | N/A |

### 6.2 Partitioning Strategy for `detections`

```sql
-- Partition by month on timestamp
CREATE TABLE detections (
    ...
) PARTITION BY RANGE (timestamp);

-- Monthly partitions
CREATE TABLE detections_2026_08 PARTITION OF detections
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE detections_2026_09 PARTITION OF detections
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

-- Drop old partitions (instant operation, no row-by-row delete)
DROP TABLE detections_2025_08;
```

**Benefits**:
- Instant partition drop vs. slow row-by-row DELETE
- Query performance improvement (partition pruning)
- Easier backup/restore of recent data only
- Vacuum only needs to process recent partitions

### 6.3 Cleanup Job Schedule

| Job | Schedule | Action |
|-----|----------|--------|
| evidence_file_cleanup | Daily 02:00 UTC | Delete expired evidence files from disk |
| detection_partition_drop | Monthly 1st | Drop partitions older than retention |
| tracked_objects_cleanup | Weekly Sunday 03:00 | Delete completed/lost tracks older than retention |
| notification_log_cleanup | Weekly Sunday 04:00 | Delete delivered/expired notifications older than 90 days |
| alert_cleanup | Monthly 1st | Delete old dismissed alerts |

### 6.4 Storage Growth Projections

Assuming 4 cameras, 15 FPS, 3 detections average per frame:

| Metric | Per Day | Per Month | Per Year |
|--------|---------|-----------|----------|
| Detection rows | ~5.2M | ~156M | ~1.9B |
| Detection storage | ~1.1 GB | ~33 GB | ~400 GB |
| With 90-day retention | — | — | Max ~100 GB |
| Tracked objects rows | ~10K | ~300K | ~3.6M |
| Evidence files (10 incidents/day) | ~200 MB | ~6 GB | ~72 GB |
| With 90-day retention | — | — | Max ~18 GB |

**Recommendation**: With 90-day detection retention and monthly partitions, total database size stays under 120 GB for the first year — manageable on a single node.

---

## 7. Sample Records

### 7.1 roles

```json
[
  {
    "id": 1,
    "name": "admin",
    "description": "Full system access including user management and configuration",
    "permissions": {
      "can_view_feed": true,
      "can_manage_cameras": true,
      "can_manage_incidents": true,
      "can_acknowledge_alerts": true,
      "can_manage_users": true,
      "can_manage_config": true,
      "can_view_audit": true,
      "can_export_reports": true
    },
    "is_system": true,
    "created_at": "2026-08-17T00:00:00Z"
  },
  {
    "id": 2,
    "name": "operator",
    "description": "Monitoring and incident response capabilities",
    "permissions": {
      "can_view_feed": true,
      "can_manage_cameras": false,
      "can_manage_incidents": true,
      "can_acknowledge_alerts": true,
      "can_manage_users": false,
      "can_manage_config": false,
      "can_view_audit": false,
      "can_export_reports": true
    },
    "is_system": true,
    "created_at": "2026-08-17T00:00:00Z"
  },
  {
    "id": 3,
    "name": "viewer",
    "description": "Read-only access to dashboard and historical data",
    "permissions": {
      "can_view_feed": true,
      "can_manage_cameras": false,
      "can_manage_incidents": false,
      "can_acknowledge_alerts": false,
      "can_manage_users": false,
      "can_manage_config": false,
      "can_view_audit": false,
      "can_export_reports": true
    },
    "is_system": true,
    "created_at": "2026-08-17T00:00:00Z"
  }
]
```

### 7.2 users

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "admin@threatplatform.local",
    "password_hash": "$2b$12$LJ3...hashed...XYZ",
    "full_name": "System Administrator",
    "role_id": 1,
    "is_active": true,
    "last_login_at": "2026-08-17T09:15:00Z",
    "failed_login_count": 0,
    "locked_until": null,
    "created_at": "2026-08-17T00:00:00Z",
    "updated_at": "2026-08-17T09:15:00Z"
  },
  {
    "id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "email": "operator1@threatplatform.local",
    "password_hash": "$2b$12$AB...hashed...MNO",
    "full_name": "Raj Sharma",
    "role_id": 2,
    "is_active": true,
    "last_login_at": "2026-08-17T08:00:00Z",
    "failed_login_count": 0,
    "locked_until": null,
    "created_at": "2026-08-17T00:00:00Z",
    "updated_at": "2026-08-17T08:00:00Z"
  }
]
```

### 7.3 camera_locations

```json
[
  {
    "id": "loc-001-uuid",
    "name": "Main Entrance Lobby",
    "building": "Academic Block A",
    "floor": "Ground",
    "zone": "Entry Zone",
    "description": "Primary entrance hall with security desk",
    "coordinates": {"lat": 28.6139, "lng": 77.2090},
    "is_active": true,
    "created_at": "2026-08-17T00:00:00Z",
    "updated_at": "2026-08-17T00:00:00Z"
  },
  {
    "id": "loc-002-uuid",
    "name": "Parking Lot B",
    "building": null,
    "floor": null,
    "zone": "External",
    "description": "Open-air parking lot, south side",
    "coordinates": {"lat": 28.6135, "lng": 77.2085},
    "is_active": true,
    "created_at": "2026-08-17T00:00:00Z",
    "updated_at": "2026-08-17T00:00:00Z"
  }
]
```

### 7.4 cameras

```json
[
  {
    "id": "cam-001-uuid",
    "name": "Lobby Cam 1",
    "location_id": "loc-001-uuid",
    "stream_url": "rtsp://192.168.1.100:554/stream1",
    "stream_type": "rtsp",
    "resolution_width": 1920,
    "resolution_height": 1080,
    "target_fps": 15,
    "status": "processing",
    "is_enabled": true,
    "last_online_at": "2026-08-17T14:30:00Z",
    "error_message": null,
    "metadata": {
      "brand": "Hikvision",
      "model": "DS-2CD2143G2-I",
      "lens_angle": 110,
      "night_vision": true
    },
    "created_at": "2026-08-17T00:00:00Z",
    "updated_at": "2026-08-17T10:00:00Z"
  },
  {
    "id": "cam-002-uuid",
    "name": "Parking Cam B1",
    "location_id": "loc-002-uuid",
    "stream_url": "rtsp://192.168.1.101:554/stream1",
    "stream_type": "rtsp",
    "resolution_width": 1280,
    "resolution_height": 720,
    "target_fps": 10,
    "status": "online",
    "is_enabled": true,
    "last_online_at": "2026-08-17T14:29:55Z",
    "error_message": null,
    "metadata": {"brand": "Dahua", "model": "IPC-HFW2431T"},
    "created_at": "2026-08-17T00:00:00Z",
    "updated_at": "2026-08-17T00:00:00Z"
  }
]
```

### 7.5 model_versions

```json
[
  {
    "id": "model-001-uuid",
    "model_name": "weapon-detector",
    "version": "1.0.0",
    "architecture": "yolov8m",
    "file_path": "/app/models/weapon_detector_v1.0.0.pt",
    "file_hash_sha256": "a3f2b8c9d4e5f67890123456789abcdef0123456789abcdef0123456789abcd",
    "input_size": 640,
    "classes": ["handgun", "rifle", "knife", "person"],
    "num_classes": 4,
    "training_dataset": "Custom weapon dataset (12K images) + COCO person subset",
    "training_epochs": 100,
    "map_score": 0.72,
    "is_active": true,
    "deployed_at": "2026-08-17T00:00:00Z",
    "deployed_by": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "notes": "Initial production model. Trained on augmented dataset with day/night variations.",
    "created_at": "2026-08-15T00:00:00Z"
  }
]
```

### 7.6 detections

```json
[
  {
    "id": 1000001,
    "camera_id": "cam-001-uuid",
    "model_version_id": "model-001-uuid",
    "timestamp": "2026-08-17T14:30:01.234Z",
    "frame_number": 45678,
    "class_label": "handgun",
    "confidence": 0.87,
    "bbox_x1": 0.35,
    "bbox_y1": 0.42,
    "bbox_x2": 0.48,
    "bbox_y2": 0.61,
    "track_id": 7,
    "is_weapon": true,
    "is_verified": true,
    "processing_time_ms": 28.5,
    "created_at": "2026-08-17T14:30:01.280Z"
  },
  {
    "id": 1000002,
    "camera_id": "cam-001-uuid",
    "model_version_id": "model-001-uuid",
    "timestamp": "2026-08-17T14:30:01.234Z",
    "frame_number": 45678,
    "class_label": "person",
    "confidence": 0.95,
    "bbox_x1": 0.20,
    "bbox_y1": 0.15,
    "bbox_x2": 0.55,
    "bbox_y2": 0.95,
    "track_id": 3,
    "is_weapon": false,
    "is_verified": false,
    "processing_time_ms": 28.5,
    "created_at": "2026-08-17T14:30:01.280Z"
  }
]
```

### 7.7 tracked_objects

```json
[
  {
    "id": 5001,
    "camera_id": "cam-001-uuid",
    "track_id": 7,
    "class_label": "handgun",
    "first_seen_at": "2026-08-17T14:29:58.000Z",
    "last_seen_at": "2026-08-17T14:30:05.500Z",
    "duration_seconds": 7.5,
    "total_frames": 105,
    "avg_confidence": 0.82,
    "min_confidence": 0.53,
    "max_confidence": 0.93,
    "last_bbox_x1": 0.36,
    "last_bbox_y1": 0.40,
    "last_bbox_x2": 0.49,
    "last_bbox_y2": 0.62,
    "is_weapon_track": true,
    "is_verified": true,
    "verification_frame_count": 4,
    "risk_score": 0.78,
    "incident_id": "inc-001-uuid",
    "status": "completed",
    "created_at": "2026-08-17T14:29:58.050Z",
    "updated_at": "2026-08-17T14:30:05.550Z"
  }
]
```

### 7.8 incidents

```json
[
  {
    "id": "inc-001-uuid",
    "camera_id": "cam-001-uuid",
    "incident_number": 1,
    "title": "Handgun detected - Main Entrance Lobby",
    "description": "Automated detection: Handgun visible for 7.5 seconds with high confidence (avg 0.82). One person present in proximity.",
    "severity": "critical",
    "status": "acknowledged",
    "risk_score": 0.78,
    "weapon_class": "handgun",
    "weapon_count": 1,
    "person_count": 1,
    "detection_confidence": 0.82,
    "started_at": "2026-08-17T14:29:58.000Z",
    "acknowledged_at": "2026-08-17T14:30:15.000Z",
    "acknowledged_by": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "resolved_at": null,
    "resolved_by": null,
    "closed_at": null,
    "closed_by": null,
    "resolution_notes": null,
    "is_false_positive": false,
    "version": 2,
    "created_at": "2026-08-17T14:30:01.500Z",
    "updated_at": "2026-08-17T14:30:15.000Z"
  }
]
```

### 7.9 evidence

```json
[
  {
    "id": "evi-001-uuid",
    "incident_id": "inc-001-uuid",
    "camera_id": "cam-001-uuid",
    "type": "snapshot",
    "file_path": "snapshots/2026/08/17/inc-001-uuid_20260817143001.jpg",
    "file_name": "inc-001-uuid_20260817143001.jpg",
    "file_size_bytes": 185320,
    "mime_type": "image/jpeg",
    "duration_seconds": null,
    "resolution_width": 1920,
    "resolution_height": 1080,
    "is_anonymized": true,
    "anonymization_failed": false,
    "frame_number": 45678,
    "annotations": [
      {"class": "handgun", "confidence": 0.87, "bbox": [0.35, 0.42, 0.48, 0.61]},
      {"class": "person", "confidence": 0.95, "bbox": [0.20, 0.15, 0.55, 0.95]}
    ],
    "captured_at": "2026-08-17T14:30:01.234Z",
    "expires_at": "2026-11-15T14:30:01.234Z",
    "metadata": {"jpeg_quality": 95, "annotation_color": "#FF0000"},
    "created_at": "2026-08-17T14:30:02.000Z"
  },
  {
    "id": "evi-002-uuid",
    "incident_id": "inc-001-uuid",
    "camera_id": "cam-001-uuid",
    "type": "clip",
    "file_path": "clips/2026/08/17/inc-001-uuid_20260817143001.mp4",
    "file_name": "inc-001-uuid_20260817143001.mp4",
    "file_size_bytes": 8542100,
    "mime_type": "video/mp4",
    "duration_seconds": 20.0,
    "resolution_width": 1920,
    "resolution_height": 1080,
    "is_anonymized": true,
    "anonymization_failed": false,
    "frame_number": null,
    "annotations": null,
    "captured_at": "2026-08-17T14:29:51.000Z",
    "expires_at": "2026-11-15T14:30:01.234Z",
    "metadata": {"codec": "h264", "fps": 15, "bitrate": 3000000, "pre_seconds": 10, "post_seconds": 10},
    "created_at": "2026-08-17T14:30:12.000Z"
  }
]
```

### 7.10 alerts

```json
[
  {
    "id": "alert-001-uuid",
    "incident_id": "inc-001-uuid",
    "camera_id": "cam-001-uuid",
    "severity": "critical",
    "title": "CRITICAL: Handgun Detected",
    "message": "A handgun has been detected at Main Entrance Lobby (Lobby Cam 1). Risk score: 0.78. 1 person in proximity. Immediate attention required.",
    "alert_type": "threat_detected",
    "is_read": true,
    "is_acknowledged": true,
    "acknowledged_by": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "acknowledged_at": "2026-08-17T14:30:15.000Z",
    "is_dismissed": false,
    "dismissed_by": null,
    "dismissed_at": null,
    "priority_order": 100,
    "expires_at": null,
    "created_at": "2026-08-17T14:30:01.600Z"
  }
]
```

### 7.11 notification_logs

```json
[
  {
    "id": 1,
    "alert_id": "alert-001-uuid",
    "user_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "channel": "websocket",
    "status": "delivered",
    "sent_at": "2026-08-17T14:30:01.650Z",
    "delivered_at": "2026-08-17T14:30:01.680Z",
    "failed_at": null,
    "failure_reason": null,
    "retry_count": 0,
    "max_retries": 3,
    "metadata": {"websocket_session_id": "ws-session-abc123", "client_ip": "192.168.1.50"},
    "created_at": "2026-08-17T14:30:01.650Z"
  },
  {
    "id": 2,
    "alert_id": "alert-001-uuid",
    "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "channel": "websocket",
    "status": "failed",
    "sent_at": "2026-08-17T14:30:01.655Z",
    "delivered_at": null,
    "failed_at": "2026-08-17T14:30:01.670Z",
    "failure_reason": "User not connected via WebSocket",
    "retry_count": 1,
    "max_retries": 3,
    "metadata": {"last_seen_online": "2026-08-17T09:15:00Z"},
    "created_at": "2026-08-17T14:30:01.655Z"
  }
]
```

### 7.12 audit_logs

```json
[
  {
    "id": 1,
    "user_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "action": "user.login",
    "resource_type": "user",
    "resource_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "description": "User logged in successfully",
    "changes": null,
    "ip_address": "192.168.1.50",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "request_id": "req-uuid-001",
    "session_id": null,
    "severity": "info",
    "timestamp": "2026-08-17T08:00:00Z"
  },
  {
    "id": 2,
    "user_id": null,
    "action": "incident.created",
    "resource_type": "incident",
    "resource_id": "inc-001-uuid",
    "description": "Incident auto-created by detection pipeline: Handgun detected at Main Entrance Lobby",
    "changes": {"after": {"status": "open", "severity": "critical", "risk_score": 0.78}},
    "ip_address": null,
    "user_agent": null,
    "request_id": null,
    "session_id": null,
    "severity": "critical",
    "timestamp": "2026-08-17T14:30:01.500Z"
  },
  {
    "id": 3,
    "user_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    "action": "incident.status_changed",
    "resource_type": "incident",
    "resource_id": "inc-001-uuid",
    "description": "Incident status changed from 'open' to 'acknowledged'",
    "changes": {"before": {"status": "open"}, "after": {"status": "acknowledged"}},
    "ip_address": "192.168.1.50",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "request_id": "req-uuid-015",
    "session_id": null,
    "severity": "info",
    "timestamp": "2026-08-17T14:30:15.000Z"
  }
]
```

---

## Summary

This database design provides:

- **12 tables** + 1 junction table covering all required data areas
- **Full referential integrity** with foreign keys and appropriate cascade rules
- **Performance-optimized** with 25+ indexes targeted at specific query patterns
- **Scalable** via monthly range partitioning on the highest-volume table (detections)
- **Retention-ready** with expiration columns and partition-based cleanup
- **Audit-compliant** with append-only audit logs and immutability enforcement
- **Flexible** via strategic JSONB columns for evolving metadata
- **Normalized to 3NF** with documented intentional denormalization for read performance

Storage projections with 90-day retention on detections: **~120 GB/year** — suitable for single-node PostgreSQL deployment.

---

**Awaiting approval to proceed with implementation (Phase 1: Foundation).**
