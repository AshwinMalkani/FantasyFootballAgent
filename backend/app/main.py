import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import activity, leagues, recs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Fantasy Hub", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(leagues.router)
app.include_router(recs.router)
app.include_router(activity.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}
