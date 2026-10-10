"""Start the combined LangTut service using the shared resolved configuration."""

import argparse

import uvicorn


def main() -> None:
    """Run one worker; optionally reload source changes during local development."""
    from app.config import Environment, config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reload", action="store_true", help="Reload local source changes")
    args = parser.parse_args()
    if args.reload and config.environment != Environment.LOCAL:
        parser.error("--reload is only available in the local environment")
    uvicorn.run(
        "asgi:create_app",
        factory=True,
        host=config.bind_host,
        port=config.port,
        workers=1,
        reload=args.reload,
        access_log=False,
        proxy_headers=bool(config.proxy_trusted_ips),
        forwarded_allow_ips=config.proxy_trusted_ips,
    )


if __name__ == "__main__":
    main()
