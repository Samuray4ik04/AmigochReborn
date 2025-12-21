"""Module entrypoint so users can run `python -m start`.

This file delegates to `main.main()` and runs it via asyncio.
"""
import asyncio
import sys
import subprocess
import os

try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("start")

if os.getenv("IS_DOCKER"):
    pass
else:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-U"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        logger.info("Requirements installed via pip")
    except Exception as e:
        logger.exception("Failed to auto-install requirements: {}", e)

try:
    from main import main as app_main
except Exception as e:
    raise RuntimeError("Failed to import project entry point 'main.main'") from e


def _run():
    asyncio.run(app_main())


if __name__ == "__main__":
    try:
        _run()
    except KeyboardInterrupt:
        logger.info("Bot stopped from panel")