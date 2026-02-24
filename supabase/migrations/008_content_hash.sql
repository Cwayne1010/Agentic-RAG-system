-- Module 3: Record Manager
-- Adds content_hash to documents table for deduplication.
-- Nullable so existing rows are unaffected.
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS content_hash text;

-- Partial unique index: enforce per-user dedup only for completed documents.
-- Excludes failed/pending/processing rows so retries are always allowed.
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_user_completed_hash
  ON documents (user_id, content_hash)
  WHERE status = 'completed';
