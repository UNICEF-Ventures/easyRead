-- PostgreSQL initialization script for EasyRead project
-- This script sets up the database with pgvector extension

-- Create the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify the extension is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Grant necessary permissions to the database user
GRANT ALL PRIVILEGES ON DATABASE easyread TO easyread_user;