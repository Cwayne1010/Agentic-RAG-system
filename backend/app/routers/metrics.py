import os
import psutil
from fastapi import APIRouter, Depends
from supabase import create_client

from app.dependencies import get_current_user

router = APIRouter()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

_process = psutil.Process()
# Prime cpu_percent — first call always returns 0.0
_process.cpu_percent()


@router.get("/metrics")
async def get_metrics(user=Depends(get_current_user)):
    mem = _process.memory_info()
    cpu = _process.cpu_percent()

    active = (
        supabase.table("documents")
        .select("id, filename, status, chunks_total, chunks_processed, created_at")
        .eq("user_id", str(user.id))
        .in_("status", ["pending", "processing"])
        .execute()
    )

    return {
        "memory_rss_mb": round(mem.rss / 1024 / 1024, 1),
        "memory_vms_mb": round(mem.vms / 1024 / 1024, 1),
        "cpu_percent": round(cpu, 1),
        "active_jobs": active.data,
    }
