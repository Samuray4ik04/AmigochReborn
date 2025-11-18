import os
import asyncio
import sys
import subprocess


try:
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("Requirements installed")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
