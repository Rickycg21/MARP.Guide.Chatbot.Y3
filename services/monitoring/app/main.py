"""
FastAPI surface for the Monitoring service.

Responsibilities:
- Expose:
    - GET /health     -> simple health check
    - GET /metrics    -> JSON MetricsSnapshot
    - GET /dashboard  -> HTML dashboard (also aliased at '/')
- On startup:
    - Initialise metrics directory/files for current run
    - Subscribe to all RAG events via RabbitMQ using common.events.consume
"""

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse

from common.config import settings
from common.events import consume
from app.models import MetricsSnapshot
from app.metrics import (
    EVENT_TYPES,
    startup_metrics,
    handle_any_event,
    get_metrics_snapshot,
    render_dashboard_html,
)

app = FastAPI(title="Monitoring Service")
logger = logging.getLogger("Monitoring")

@app.on_event("startup")
async def on_startup() -> None:
    """
    FastAPI startup hook.

    - Ensure /data/metrics, metrics.json, and events.jsonl exist.
    - Start one consumer task per event type (true pub/sub).
    - Metrics always start from zero for each run.
    """
    await startup_metrics()

    for event_type in EVENT_TYPES:
        logger.info("Monitoring subscribing to event_type=%s", event_type)
        # Each consume(...) call runs forever; we schedule them as background tasks.
        asyncio.create_task(consume(event_type, handle_any_event))

@app.get("/health")
async def health() -> dict:
    """
    Basic health check for Docker and uptime monitoring.
    """
    return {"status": "ok", "service": settings.service_name}

@app.get("/metrics", response_model=MetricsSnapshot)
async def metrics() -> JSONResponse:
    """
    Return the current metrics snapshot as JSON.
    """
    snap = await get_metrics_snapshot()
    return JSONResponse(snap.model_dump())

@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """
    Render the HTML monitoring dashboard.
    """
    html = await render_dashboard_html()
    return HTMLResponse(content=html)