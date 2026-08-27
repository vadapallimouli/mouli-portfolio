import os
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def test_root_api():
    response = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert response.status_code == 200
    assert response.json()["message"] == "Mouli portfolio API"


def test_contact_delivery_configuration_state():
    response = requests.post(f"{BASE_URL}/api/contact", json={
        "name": "Test Visitor", "email": "visitor@example.com",
        "subject": "Hello portfolio", "message": "This is a valid test message."
    }, timeout=15)
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert response.json()["status"] == "success"
    else:
        assert "not configured" in response.json()["detail"]


def test_contact_validation():
    response = requests.post(f"{BASE_URL}/api/contact", json={
        "name": "x", "email": "not-an-email", "subject": "x", "message": "short"
    }, timeout=15)
    assert response.status_code == 422