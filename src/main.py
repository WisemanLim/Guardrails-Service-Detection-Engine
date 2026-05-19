from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from .api import detect, health, normalize
from .config import settings
from .detectors.registry import registry as detector_registry
from .detectors.bootstrap import bootstrap_builtins


def create_app() -> FastAPI:
    app = FastAPI(
        title="Guardrails Detection Engine",
        version="0.1.0",
        default_response_class=ORJSONResponse,
    )
    bootstrap_builtins(detector_registry, enabled_domains=settings.enabled_domains)
    app.include_router(health.router)
    app.include_router(normalize.router)
    app.include_router(detect.router)
    return app


app = create_app()
