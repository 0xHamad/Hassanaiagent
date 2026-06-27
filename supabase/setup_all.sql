
-- Run once in Supabase Dashboard → SQL Editor → New query → Run
-- https://supabase.com/dashboard/project/nbfzdezmvggmmvhkkvbt/sql/new

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

CREATE TABLE IF NOT EXISTS hassan_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES hassan_users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'New Chat',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hassan_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES hassan_conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hassan_conv_user ON hassan_conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_hassan_msg_conv ON hassan_messages(conversation_id, created_at ASC);

ALTER TABLE hassan_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE hassan_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE hassan_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE hassan_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_insert_users" ON hassan_users FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "allow_select_users" ON hassan_users FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "allow_insert_sessions" ON hassan_sessions FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "allow_select_sessions" ON hassan_sessions FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "allow_delete_sessions" ON hassan_sessions FOR DELETE TO anon, authenticated USING (true);
CREATE POLICY "allow_insert_conversations" ON hassan_conversations FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "allow_select_conversations" ON hassan_conversations FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "allow_update_conversations" ON hassan_conversations FOR UPDATE TO anon, authenticated USING (true);
CREATE POLICY "allow_delete_conversations" ON hassan_conversations FOR DELETE TO anon, authenticated USING (true);
CREATE POLICY "allow_insert_messages" ON hassan_messages FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "allow_select_messages" ON hassan_messages FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "allow_delete_messages" ON hassan_messages FOR DELETE TO anon, authenticated USING (true);
