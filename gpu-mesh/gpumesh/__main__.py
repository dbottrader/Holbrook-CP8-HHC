"""``python -m gpumesh`` starts the coordinator."""

from __future__ import annotations

import uvicorn

from gpumesh.settings import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "gpumesh.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        workers=1,
    )


if __name__ == "__main__":
    main()
