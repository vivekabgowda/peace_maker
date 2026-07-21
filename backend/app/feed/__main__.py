"""Entrypoint: ``python -m app.feed`` runs the Feed Service (single instance)."""

from __future__ import annotations

import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    # A single worker — the feed is a singleton; horizontal instances stand by
    # on the Redis lock and take over on failover.
    uvicorn.run(
        "app.feed.app:app",
        host=settings.host,
        port=8001,
        workers=1,
        log_config=None,
    )


if __name__ == "__main__":
    main()
