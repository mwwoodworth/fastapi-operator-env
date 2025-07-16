import os
from supabase import create_client
from utils.fake_supabase import FakeSupabaseClient

from core.settings import Settings

settings = Settings()

url = settings.SUPABASE_URL
key = settings.SUPABASE_SERVICE_KEY

if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
if os.getenv("USE_FAKE_SUPABASE") == "1" or "example.com" in url:
    supabase = FakeSupabaseClient()
else:
    supabase = create_client(url, key)
