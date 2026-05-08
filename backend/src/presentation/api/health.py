from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck():
    return {
        "status": "ok"
    }