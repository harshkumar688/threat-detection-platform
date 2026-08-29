-- =============================================================================
-- PostgreSQL Initialization Script
-- Runs ONLY on first container startup (when pgdata volume is empty)
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set timezone
SET timezone = 'UTC';
ALTER DATABASE threat_detection SET timezone TO 'UTC';

-- Confirmation
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully with uuid-ossp and pgcrypto extensions.';
END $$;
