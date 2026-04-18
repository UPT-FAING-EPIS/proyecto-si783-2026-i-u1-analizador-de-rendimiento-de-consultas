-- MySQL initialization script for query_analyzer
-- Creates qa and analyst users with all privileges on query_analyzer database
-- This script runs automatically via Docker entrypoint

-- Create qa user if it doesn't exist (MySQL 8 syntax)
-- The MYSQL_USER environment variable should have already created this user,
-- but this script ensures it exists with proper privileges
CREATE USER IF NOT EXISTS 'qa'@'%' IDENTIFIED BY 'QAnalyze';
GRANT ALL PRIVILEGES ON query_analyzer.* TO 'qa'@'%';

-- Create analyst user for integration tests
CREATE USER IF NOT EXISTS 'analyst'@'%' IDENTIFIED BY 'mysql123';
GRANT ALL PRIVILEGES ON query_analyzer.* TO 'analyst'@'%';

-- Flush privileges to apply changes immediately
FLUSH PRIVILEGES;
