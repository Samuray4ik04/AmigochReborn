import random
import os
from aiogram import types
import datetime
import time
from dotenv import load_dotenv

load_dotenv()


def user(message: types.Message):
    return message.from_user


def now_time():
    return datetime.datetime.now()


def format_timedelta(td: datetime.timedelta) -> str:
    """Format timedelta to human-friendly string like '1d 02h 03m 04s'."""
    total_seconds = int(td.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours:02}h")
    parts.append(f"{minutes:02}m")
    parts.append(f"{seconds:02}s")
    return " ".join(parts)

def version():
    return f"0.5.2-dev"