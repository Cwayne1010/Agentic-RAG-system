-- Add chunk progress tracking columns for real-time ingestion feedback
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS chunks_total integer,
  ADD COLUMN IF NOT EXISTS chunks_processed integer DEFAULT 0;
