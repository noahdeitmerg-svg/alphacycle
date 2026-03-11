import os
from supabase import create_client, Client


SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://epcvkgtneeafgpjjrfiq.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

supabase = None
if SUPABASE_SERVICE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception as e:
        import logging
        logging.warning(f"Supabase init failed: {e}")


# SQL schema for reference (to be executed in Supabase SQL editor)
#
# -- Email captures (auch ohne Auth)
# CREATE TABLE IF NOT EXISTS email_captures (
#     id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
#     email TEXT UNIQUE NOT NULL,
#     source TEXT DEFAULT 'dashboard',
#     arc_score INTEGER,
#     zone TEXT,
#     created_at TIMESTAMPTZ DEFAULT NOW(),
#     beehiiv_synced BOOLEAN DEFAULT FALSE
# );
#
# -- User profiles (verknüpft mit Supabase Auth)
# CREATE TABLE IF NOT EXISTS user_profiles (
#     id UUID REFERENCES auth.users(id) PRIMARY KEY,
#     email TEXT,
#     plan TEXT DEFAULT 'free',
#     stripe_customer_id TEXT,
#     stripe_subscription_id TEXT,
#     subscription_status TEXT DEFAULT 'inactive',
#     current_period_end TIMESTAMPTZ,
#     created_at TIMESTAMPTZ DEFAULT NOW()
# );
#
# -- Alert log
# CREATE TABLE IF NOT EXISTS alert_log (
#     id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
#     triggered_at TIMESTAMPTZ DEFAULT NOW(),
#     arc_score INTEGER,
#     zone_from TEXT,
#     zone_to TEXT,
#     emails_sent INTEGER DEFAULT 0
# );
#
# -- Row Level Security
# ALTER TABLE email_captures ENABLE ROW LEVEL SECURITY;
# ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
#
# -- Policies
# CREATE POLICY "Users can read own profile"
# ON user_profiles FOR SELECT
# USING (auth.uid() = id);
#
# CREATE POLICY "Users can update own profile"
# ON user_profiles FOR UPDATE
# USING (auth.uid() = id);

