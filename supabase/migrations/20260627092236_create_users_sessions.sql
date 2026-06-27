
CREATE TABLE IF NOT EXISTS hassan_users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hassan_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES hassan_users(id) ON DELETE CASCADE,
  token TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ DEFAULT now() + interval '30 days'
);

ALTER TABLE hassan_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE hassan_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_insert_users" ON hassan_users FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "allow_select_users" ON hassan_users FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY "allow_insert_sessions" ON hassan_sessions FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "allow_select_sessions" ON hassan_sessions FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "allow_delete_sessions" ON hassan_sessions FOR DELETE TO anon, authenticated USING (true);
