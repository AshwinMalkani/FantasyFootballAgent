from fastapi import APIRouter

from ..services.news import build_news

router = APIRouter(prefix="/api")


@router.get("/news")
def news(days: int = 10, bench: bool = True):
    return build_news(days=days, include_bench=bench)
