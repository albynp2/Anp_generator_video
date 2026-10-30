"""Parsing & format timecode (HH:MM:SS, MM:SS, atau detik)."""
from __future__ import annotations

import re

_INT = re.compile(r"^\d{1,4}$")
_SEC = re.compile(r"^\d{1,5}(\.\d{1,3})?$")


def parse_timecode(value) -> float:
    """'00:03:25' -> 205.0 | '03:25' -> 205.0 | '205' -> 205.0 | '00:03:25.5' -> 205.5.

    Raise ValueError bila format salah.
    """
    if value is None:
        raise ValueError("empty")
    s = str(value).strip().replace(",", ".")
    if not s:
        raise ValueError("empty")
    parts = s.split(":")
    if len(parts) > 3:
        raise ValueError("too many parts")
    for p in parts[:-1]:
        if not _INT.match(p):
            raise ValueError("bad part")
    if not _SEC.match(parts[-1]):
        raise ValueError("bad seconds")
    nums = [float(p) for p in parts]
    if len(parts) >= 2 and nums[-1] >= 60:
        raise ValueError("seconds >= 60")
    if len(parts) == 3 and nums[1] >= 60:
        raise ValueError("minutes >= 60")
    total = 0.0
    for n in nums:
        total = total * 60 + n
    return round(total, 3)


def format_timecode(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
