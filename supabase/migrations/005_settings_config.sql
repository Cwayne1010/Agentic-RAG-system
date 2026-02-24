-- Add per-provider configuration to app_settings
ALTER TABLE app_settings
  ADD COLUMN IF NOT EXISTS llm_base_url        TEXT NOT NULL DEFAULT 'https://openrouter.ai/api/v1',
  ADD COLUMN IF NOT EXISTS llm_api_key         TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS embedding_base_url  TEXT NOT NULL DEFAULT 'https://openrouter.ai/api/v1',
  ADD COLUMN IF NOT EXISTS embedding_api_key   TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS embedding_dimensions INT NOT NULL DEFAULT 1536;

-- Migrate existing OpenAI model IDs to OpenRouter format
UPDATE app_settings SET embedding_model = 'openai/text-embedding-3-small'
  WHERE embedding_model = 'text-embedding-3-small';
UPDATE app_settings SET embedding_model = 'openai/text-embedding-3-large'
  WHERE embedding_model = 'text-embedding-3-large';
