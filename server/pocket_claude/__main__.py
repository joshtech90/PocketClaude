"""Entry point: `python -m pocket_claude`."""
import uvicorn

from pocket_claude.config import settings


def main() -> None:
    uvicorn.run(
        "pocket_claude.server:app",
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
        reload=settings.dev_reload,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )


if __name__ == "__main__":
    main()
