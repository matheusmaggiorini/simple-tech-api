"""Tests for Simple Tech API."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from api.endpoints import state
from api.main import app

client = TestClient(app)


@pytest.fixture
def auth_headers():
    email = "test@simpletech.dev"
    password = "testpass123"

    register = client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": email, "password": password},
    )
    if register.status_code == 200:
        token = register.json()["access_token"]
    else:
        login = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

    user_id = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["id"]

    state.set_current_user(user_id)
    state.global_processed_df = None
    state.global_prediction_model = None
    state.global_historical_stats = None

    yield {"Authorization": f"Bearer {token}"}

    state.clear_session(user_id)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_register_and_login():
    email = "newuser@simpletech.dev"
    response = client.post(
        "/api/auth/register",
        json={"name": "New User", "email": email, "password": "secure123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "secure123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email


def test_protected_route_without_token():
    response = client.get("/api/data/status")
    assert response.status_code == 401


def test_data_status_without_upload(auth_headers):
    response = client.get("/api/data/status", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["has_data"] is False


def test_view_processed_without_data(auth_headers):
    response = client.get("/api/data/view_processed", headers=auth_headers)
    assert response.status_code == 404


def test_upload_csv_bundle(auth_headers):
    csv_content = """data,descricao,entrada,saida
2024-01-01,Venda A,1000.00,0.00
2024-01-02,Fornecedor,0.00,500.00
2024-01-03,Venda B,1500.00,0.00
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        with open(temp_path, "rb") as f:
            response = client.post(
                "/api/data/upload_excel_bundle",
                headers=auth_headers,
                files={"file": ("dados_teste.csv", f, "text/csv")},
            )
        assert response.status_code == 200

        status = client.get("/api/data/status", headers=auth_headers)
        assert status.json()["has_data"] is True
    finally:
        os.remove(temp_path)


def test_prediction_without_data(auth_headers):
    response = client.post(
        "/api/predictions/cashflow",
        headers=auth_headers,
        json={"future_days": 30},
    )
    assert response.status_code == 400
