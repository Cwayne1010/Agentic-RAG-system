-- Add metadata column to messages for persisting tool call state
ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT NULL;
