import os
from fastapi import Header, HTTPException
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


async def get_current_user(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    try:
        result = supabase.auth.get_user(token)
        return result.user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
