from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def post_detect(text: str, locale: str = "ko-KR", io_type: str = "input") -> dict:
    r = client.post(
        "/detect",
        json={"text": text, "domain": "global", "locale": locale, "io_type": io_type},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_korean_rrn_detected():
    body = post_detect("제 주민등록번호는 900101-1234567 입니다.", locale="ko-KR")
    assert any(m["sub_category"] == "national_id_kr" for m in body["matches"])
    assert body["risk_score"] >= 0.9


def test_us_ssn_detected():
    body = post_detect("My SSN is 123-45-6789.", locale="en")
    assert any(m["sub_category"] == "ssn_us" for m in body["matches"])


def test_email_detected():
    body = post_detect("Contact me at user@example.com.", locale="en")
    assert any(m["sub_category"] == "email" for m in body["matches"])


def test_card_luhn_pass():
    body = post_detect("Card: 4111 1111 1111 1111", locale="en")
    assert any(m["sub_category"] == "card_number" for m in body["matches"])


def test_card_luhn_fail():
    body = post_detect("Number 1234 5678 9012 3456 is not a card.", locale="en")
    assert not any(m["sub_category"] == "card_number" for m in body["matches"])


def test_benign_passes_through():
    body = post_detect("오늘 회의는 3시입니다.", locale="ko-KR")
    assert body["risk_score"] == 0


def test_normalize_endpoint_strips_fullwidth():
    r = client.post("/normalize", json={"text": "９００１０１-1234567", "locale": "ko-KR"})
    assert r.status_code == 200
    assert "900101-1234567" in r.json()["normalized_text"]


def test_health_lists_detectors():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "pii.id.rrn.kr" in body["detectors"]
