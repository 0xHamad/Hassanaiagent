-- Admin features: signup limits, block users, IP/device tracking
ALTER TABLE hassan_users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE hassan_sessions ADD COLUMN IF NOT EXISTS ip_address TEXT NOT NULL DEFAULT '';
ALTER TABLE hassan_sessions ADD COLUMN IF NOT EXISTS user_agent TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS hassan_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

INSERT INTO hassan_settings (key, value) VALUES ('signup_limit', '100')
ON CONFLICT (key) DO NOTHING;

ALTER TABLE hassan_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow_all_settings" ON hassan_settings FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

CREATE POLICY "allow_update_users" ON hassan_users FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "allow_delete_users" ON hassan_users FOR DELETE TO anon, authenticated USING (true);
