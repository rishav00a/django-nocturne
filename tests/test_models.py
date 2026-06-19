import pytest
from django.utils import timezone

from nocturne.models import AnomalyEvent, HealthSnapshot, LogEntry, WebhookConfig, WebhookEvent


@pytest.mark.django_db
def test_logentry_str():
    entry = LogEntry.objects.create(
        service_name="auth-service",
        level="ERROR",
        message="test error",
        request_path="/api/v1/login",
        status_code=500,
    )
    assert "ERROR" in str(entry)
    assert "auth-service" in str(entry)


@pytest.mark.django_db
def test_anomaly_event_str():
    anomaly = AnomalyEvent.objects.create(
        service_name="payment-service",
        severity="CRITICAL",
        z_score=4.5,
        error_count=40,
        window_start=timezone.now(),
        window_end=timezone.now(),
    )
    assert "CRITICAL" in str(anomaly)
    assert "payment-service" in str(anomaly)


@pytest.mark.django_db
def test_webhook_event_links_to_anomaly():
    anomaly = AnomalyEvent.objects.create(
        service_name="api-gateway",
        severity="HIGH",
        z_score=3.1,
        error_count=20,
        window_start=timezone.now(),
        window_end=timezone.now(),
    )
    config = WebhookConfig.objects.create(name="Test", url="https://example.com/hook")
    event = WebhookEvent.objects.create(
        anomaly=anomaly,
        webhook_config=config,
        payload={"event": "anomaly.detected"},
        success=True,
        response_status=200,
    )
    assert event.anomaly == anomaly
    assert event.success is True
    assert "✓" in str(event)


@pytest.mark.django_db
def test_health_snapshot_created():
    snap = HealthSnapshot.objects.create(
        service_name="auth-service",
        health_score=65.5,
        error_rate=5.0,
        request_count=100,
        anomaly_count=1,
    )
    assert snap.health_score == 65.5
    assert "auth-service" in str(snap)
