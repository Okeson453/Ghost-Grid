import asyncio
from types import SimpleNamespace

from nuclear.models import NuclearEvent, NuclearReason
from telegram import alerts


def test_send_nuclear_alert_accepts_cooldown_and_includes_it(monkeypatch):
    captured = {}

    async def fake_send(text: str) -> None:
        captured["text"] = text

    monkeypatch.setattr(alerts, "_send", fake_send)

    event = NuclearEvent(
        reason=NuclearReason.MANUAL_TELEGRAM,
        timestamp_ms=1_234_567_890,
        positions_closed=2,
        portfolio_pnl=-120.0,
        equity_at_fire=9_800.0,
    )
    cooldown = SimpleNamespace(remaining_s=900)

    asyncio.run(alerts.send_nuclear_alert(event, cooldown))

    assert "NUCLEAR EXIT" in captured["text"]
    assert "Cooldown" in captured["text"]
    assert "15 minutes" in captured["text"] or "15m" in captured["text"]


def test_rate_limiter_suppresses_excess_messages(monkeypatch):
    sent_messages = []

    class FakeBot:
        async def send_message(self, chat_id, text, parse_mode=None):
            sent_messages.append(text)

    monkeypatch.setattr(alerts, "_bot", FakeBot())
    monkeypatch.setattr(
        alerts,
        "_rate_limiter",
        alerts.TelegramRateLimiter(max_messages=1, window_seconds=60),
    )
    monkeypatch.setattr(alerts.time, "monotonic", lambda: 1.0)

    asyncio.run(alerts._send("first"))
    asyncio.run(alerts._send("second"))

    assert sent_messages == ["first"]
