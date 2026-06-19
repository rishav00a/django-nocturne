import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from nocturne.models import AnomalyEvent, LogEntry, WebhookConfig, WebhookEvent
from django.utils import timezone


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("admin", "admin@test.com", "password")


@pytest.fixture
def api_client(superuser):
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.fixture
def sample_log(db):
    return LogEntry.objects.create(
        service_name="test-svc",
        level="ERROR",
        message="test error",
        request_path="/api/v1/test",
        status_code=500,
        response_time_ms=250.0,
        exception_type="ValueError",
        exception_message="test error",
        stacktrace="Traceback (most recent call last):\n  ...\nValueError: test error",
    )


@pytest.mark.django_db
def test_health_endpoint(api_client):
    resp = api_client.get("/nocturne/api/health/")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_logs" in data
    assert "error_rate" in data
    assert "active_anomalies" in data


@pytest.mark.django_db
def test_log_list_endpoint(api_client, sample_log):
    resp = api_client.get("/nocturne/api/logs/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    # List response must NOT include stacktrace (light serializer)
    assert "stacktrace" not in data["results"][0]


@pytest.mark.django_db
def test_log_detail_includes_stacktrace(api_client, sample_log):
    resp = api_client.get(f"/nocturne/api/logs/{sample_log.id}/")
    assert resp.status_code == 200
    data = resp.json()
    assert "stacktrace" in data
    assert data["exception_type"] == "ValueError"


@pytest.mark.django_db
def test_anomaly_list_endpoint(api_client):
    AnomalyEvent.objects.create(
        service_name="test-svc",
        severity="HIGH",
        z_score=3.5,
        error_count=30,
        window_start=timezone.now(),
        window_end=timezone.now(),
    )
    resp = api_client.get("/nocturne/api/anomalies/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.django_db
def test_webhook_events_endpoint(api_client):
    resp = api_client.get("/nocturne/api/webhooks/events/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.django_db
def test_webhook_config_crud(api_client):
    # Create
    resp = api_client.post("/nocturne/api/webhooks/", {
        "name": "Test Hook",
        "url": "https://example.com/hook",
        "is_active": True,
    })
    assert resp.status_code == 201
    pk = resp.json()["id"]

    # Read list
    resp = api_client.get("/nocturne/api/webhooks/")
    assert resp.status_code == 200
    assert any(w["id"] == pk for w in resp.json())

    # Update
    resp = api_client.put(f"/nocturne/api/webhooks/{pk}/", {"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Delete
    resp = api_client.delete(f"/nocturne/api/webhooks/{pk}/")
    assert resp.status_code == 204


@pytest.mark.django_db
def test_dashboard_data_includes_health_trends(api_client, sample_log):
    resp = api_client.get("/nocturne/api/dashboard/data/?timeframe=1h")
    assert resp.status_code == 200
    data = resp.json()
    assert "health_trends" in data
    assert "timeframe" in data
    assert "health_scores" in data
