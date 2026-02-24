-- Clear existing plain-text API keys.
-- After this migration, API keys are encrypted by the backend before storage.
-- Users must re-enter their API keys via the Settings panel.
UPDATE app_settings SET llm_api_key = '', embedding_api_key = '' WHERE id = 1;
