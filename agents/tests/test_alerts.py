from agents import alerts
from agents.alerts import send_telegram, alert_if_risky

def test_sin_config(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert send_telegram("hola") == {"sent": False, "reason": "sin-config"}

def test_envio_mock(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(alerts, "_post", lambda url, payload, timeout=8: {"ok": True})
    assert send_telegram("hola")["sent"] is True

def test_bajo_umbral_no_envia(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    r = alert_if_risky("wallet", "0xabc", "ethereum", 10, [])
    assert r == {"sent": False, "reason": "bajo-umbral"}
