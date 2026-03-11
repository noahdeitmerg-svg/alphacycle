import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client


security = HTTPBearer(auto_error=False)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://epcvkgtneeafgpjjrfiq.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    if not credentials:
        return None
    try:
        token = credentials.credentials
        user = supabase_admin.auth.get_user(token)
        return user.user
    except Exception:
        return None


async def require_auth(credentials: HTTPAuthorizationCredentials = Security(security)):
    user = await get_current_user(credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_paid(credentials: HTTPAuthorizationCredentials = Security(security)):
    user = await require_auth(credentials)
    profile = (
        supabase_admin.table("user_profiles")
        .select("plan")
        .eq("id", str(user.id))
        .single()
        .execute()
    )
    if not profile.data or profile.data.get("plan") != "paid":
        raise HTTPException(status_code=403, detail="Paid subscription required")
    return user

