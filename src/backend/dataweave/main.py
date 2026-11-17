from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dataweave import __version__
from dataweave.api import router
from dataweave.config import settings
from dataweave.observability import application_logger, configure_file_logging


def create_app() -> FastAPI:
    configure_file_logging()
    application_logger.info("DataWeave API starting; data_dir=%s log_dir=%s", settings.data_dir, settings.log_dir)
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="DataWeave 论文入库与结构化提取 Demo API",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()

