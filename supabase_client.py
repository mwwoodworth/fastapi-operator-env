from supabase import create_client

from core.settings import Settings

settings = Settings()

url = settings.SUPABASE_URL
key = settings.SUPABASE_SERVICE_KEY

if not url or not key:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

supabase = create_client(url, key)
