-- Add map_model setting for bulk document analysis (used in map-reduce phase)
ALTER TABLE app_settings
  ADD COLUMN IF NOT EXISTS map_model TEXT NOT NULL DEFAULT 'google/gemini-flash-1.5';
