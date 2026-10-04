from app.core.money import format_amount, to_minor
from app.log_setup import redact
from app.security.ratelimit import RateLimiter
from app.security.sanitize import clean_text, contains_card_number


def test_clean_text_strips_bidi_and_controls():
    assert clean_text("Кафе‮​  \x00\tМосква", 40) == "Кафе Москва"
    assert clean_text("  a  ", 40) == "a"
    assert clean_text("x" * 100, 10) == "x" * 10


def test_card_numbers_detected():
    assert contains_card_number("4111 1111 1111 1111")
    assert contains_card_number("карта 5555-5555-5555-4444")
    assert not contains_card_number("Карта Тинькофф")
    assert not contains_card_number("1234 5678 9012 3456")  # fails Luhn
    assert not contains_card_number("300")


def test_redact_removes_secrets_and_ids():
    fake_token = "123456789:" + "AAHdq" + "x" * 30
    fake_mail = "x" + "@" + "y.com"
    line = f"tma query_id=AA&user=%7B%22id%22%3A1%7D&hash=abc {fake_token} chat_id=777 {fake_mail}"
    out = redact(line)
    for leaked in ("abc", "AAHdq", "777", fake_mail, "%7B"):
        assert leaked not in out


def test_money_helpers():
    assert to_minor("300", "RUB") == 30000
    assert to_minor("1.005", "RUB") == 101
    assert to_minor("1500", "JPY") == 1500
    assert to_minor("1.2345", "KWD") == 1235
    assert format_amount(-30000, "RUB") == "−300 ₽"
    assert format_amount(14832050, "RUB") == "148 320,50 ₽"
    assert format_amount(500, "USD", signed=True) == "+5 $"


def test_rate_limiter():
    rl = RateLimiter(limit=2, window_seconds=10)
    assert rl.allow("k", now=0) and rl.allow("k", now=1)
    assert not rl.allow("k", now=2)
    assert rl.allow("k", now=12)
