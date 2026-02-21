-- Global application settings (single row, no RLS)
-- Accessed only via service role key from the backend

CREATE TABLE app_settings (
  id              INTEGER PRIMARY KEY DEFAULT 1,
  embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
  chat_model      TEXT NOT NULL DEFAULT 'google/gemini-1.5-flash',
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO app_settings (id, embedding_model, chat_model)
VALUES (1, 'text-embedding-3-small', 'google/gemini-1.5-flash')
ON CONFLICT (id) DO NOTHING;

-- Auto-update updated_at (reuses function from migration 002)
CREATE TRIGGER app_settings_updated_at
  BEFORE UPDATE ON app_settings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
