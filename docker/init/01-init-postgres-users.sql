-- PostgreSQL initialization script for query_analyzer
-- Creates qa and postgres users with SUPERUSER privileges
-- This script runs automatically via Docker entrypoint

-- Create qa user if it doesn't exist (used by seed.sh)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = 'qa') THEN
        CREATE USER qa WITH PASSWORD 'QAnalyze';
    END IF;
END
$$;

-- Create postgres user if it doesn't exist (used by integration tests)
-- Note: postgres user is usually created by default, but we ensure it exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = 'postgres') THEN
        CREATE USER postgres WITH PASSWORD 'postgres123';
    ELSE
        -- Update password in case it changed
        ALTER USER postgres WITH PASSWORD 'postgres123';
    END IF;
END
$$;

-- Grant SUPERUSER and CREATEDB privileges to both users
ALTER USER qa WITH SUPERUSER CREATEDB;
ALTER USER postgres WITH SUPERUSER CREATEDB;

-- Grant all privileges on the query_analyzer database
GRANT ALL PRIVILEGES ON DATABASE query_analyzer TO qa;
GRANT ALL PRIVILEGES ON DATABASE query_analyzer TO postgres;
