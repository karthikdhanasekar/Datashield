-- DataShield OSINT — PostgreSQL Initialization
-- This file runs once when the PostgreSQL container first starts

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable trigram for full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable pgcrypto for additional cryptographic functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create initial admin user (password will be set via API or environment)
-- Actual tables are created by Alembic migrations (see backend/alembic/)
-- This file just ensures extensions are available.

COMMENT ON DATABASE datashield IS 'DataShield OSINT — Privacy Protection Platform';
