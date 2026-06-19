import pytest
from datetime import timedelta

from django.utils import timezone

from nocturne.detection import compute_health_score, run_detection
from nocturne.models import AnomalyEvent, LogEntry


def _make_logs(service, level, count, offset_mins=0):
    now = timezone.now() - timedelta(minutes=offset_mins)
    entries = [
        LogEntry(
            service_name=service,
            level=level,
            message=f"test {i}",
            request_path="/test/",
            status_code=500 if level == "ERROR" else 200,
            response_time_ms=100.0,
        )
        for i in range(count)
    ]
    created = LogEntry.objects.bulk_create(entries)
    # Fix timestamps
    from django.db import connection
    table = LogEntry._meta.db_table
    with connection.cursor() as cursor:
        cursor.executemany(
            f"UPDATE {table} SET timestamp = %s WHERE id = %s",
            [(now.isoformat(sep=" "), obj.id) for obj in created],
        )
    return created


@pytest.mark.django_db
def test_compute_health_score_healthy_service():
    _make_logs("healthy-svc", "INFO", 50)
    score = compute_health_score("healthy-svc")
    assert 0 <= score <= 100


@pytest.mark.django_db
def test_compute_health_score_degraded():
    _make_logs("degraded-svc", "INFO", 20)
    _make_logs("degraded-svc", "ERROR", 40)  # >50% error rate
    score = compute_health_score("degraded-svc")
    assert score < 60


@pytest.mark.django_db
def test_run_detection_creates_anomaly():
    # Inject a spike: many errors concentrated in a short bucket
    now = timezone.now()
    spike_base = now - timedelta(minutes=2)
    entries = [
        LogEntry(
            service_name="spike-svc",
            level="ERROR",
            message="spike error",
            request_path="/api/test/",
            status_code=500,
            response_time_ms=1000.0,
        )
        for _ in range(45)
    ]
    created = LogEntry.objects.bulk_create(entries)
    from django.db import connection
    table = LogEntry._meta.db_table
    with connection.cursor() as cursor:
        cursor.executemany(
            f"UPDATE {table} SET timestamp = %s WHERE id = %s",
            [(spike_base.isoformat(sep=" "), obj.id) for obj in created],
        )
    anomalies = run_detection()
    svc_anomalies = [a for a in anomalies if a.service_name == "spike-svc"]
    assert len(svc_anomalies) >= 1
    assert svc_anomalies[0].z_score >= 2.0
