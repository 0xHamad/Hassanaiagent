-- Per-user LLM settings + admin-visible passwords
ALTER TABLE hassan_users ADD COLUMN IF NOT EXISTS plain_password TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS hassan_user_settings (
  user_id UUID PRIMARY KEY REFERENCES hassan_users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL DEFAULT 'gemini',
  api_key TEXT NOT NULL DEFAULT '',
  cursor_api_key TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  base_url TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE hassan_user_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_user_settings" ON hassan_user_settings FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
