"""Module entrypoint so users can run `python -m start`.

This file delegates to `main.main()` and runs it via asyncio.
"""
import asyncio
import sys
import os
try:
    from loguru import logger
except ImportError:
    print("loguru is not installed.")
    class _Logger:
        def info(self, msg: str) -> None:
            print(msg)
    logger = _Logger()

try:
    # import the project's main coroutine
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
