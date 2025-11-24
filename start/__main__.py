"""Module entrypoint so users can run `python -m start`.

This file delegates to `main.main()` and runs it via asyncio.
"""
import asyncio
import sys
import subprocess

try:
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-U"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("Requirements installed")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

try:
    # import the project's main coroutine
    from main import main as app_main
except Exception as e:
    raise RuntimeError("Failed to import project entry point 'main.main'") from e


def _run():
    asyncio.run(app_main())


if __name__ == "__main__":
    _run()
