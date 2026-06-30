"""Daily cost guardrail.

A hard kill-switch so a traffic spike (or abuse) can't run up the Fireworks bill.
Each chat turn's spend is *estimated* from token counts and accumulated against a
configurable daily cap (USD, per UTC day). Once the cap is reached, new chat turns
are refused with 429 until the next day.

In-memory and per-process — fine for a single-container deployment. Behind multiple
workers you'd back this with a shared store (Redis); see SECURITY.md.

The cost is an estimate (token counts approximated from text length), so set the
per-token prices to match your provider and treat the cap as a safety net, not
billing-grade accounting.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from fastapi import HTTPException

from .config import get_settings


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def estimate_tokens(text: str) -> int:
    # ~4 chars/token is a good rough rule for English; good enough for a cap.
    return max(1, len(text or "") // 4)


def estimate_cost_usd(prompt_text: str, completion_text: str) -> float:
    s = get_settings()
    in_usd = estimate_tokens(prompt_text) * s.usd_per_million_input_tokens
    out_usd = estimate_tokens(completion_text) * s.usd_per_million_output_tokens
    return (in_usd + out_usd) / 1_000_000


class CostMeter:
    """Thread-safe accumulator of estimated spend for the current UTC day."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._day = _utc_day()
        self._spent = 0.0

    def _roll_locked(self) -> None:
        today = _utc_day()
        if today != self._day:
            self._day, self._spent = today, 0.0

    def spent_today(self) -> float:
        with self._lock:
            self._roll_locked()
            return self._spent

    def over_cap(self) -> bool:
        cap = get_settings().daily_cost_cap_usd
        if cap <= 0:  # 0 / negative disables the cap
            return False
        return self.spent_today() >= cap

    def add(self, usd: float) -> None:
        if usd <= 0:
            return
        with self._lock:
            self._roll_locked()
            self._spent += usd


# Process-wide singleton.
METER = CostMeter()


async def cost_guard() -> None:
    """FastAPI dependency: refuse new chat turns once the daily cap is hit."""
    if METER.over_cap():
        raise HTTPException(
            status_code=429,
            detail="The assistant has reached its daily usage limit. Please try again tomorrow.",
        )
