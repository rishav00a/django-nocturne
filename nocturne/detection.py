import hashlib
import hmac
import json
import logging
from datetime import timedelta

import numpy as np
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_apm_setting(key, default=None):
    return getattr(settings, "NOCTURNE", {}).get(key, default)


def _severity_from_z(z_score):
    if z_score >= 4.0:
        return "CRITICAL"
    if z_score >= 3.0:
        return "HIGH"
    return "MEDIUM"


# ---------------------------------------------------------------------------
# Layer 1: Statistical Z-score anomaly detection
# ---------------------------------------------------------------------------

def run_detection():
    from .models import AnomalyEvent, LogEntry

    threshold = _get_apm_setting("ANOMALY_THRESHOLD", 2.0)
    now = timezone.now()
    window_start = now - timedelta(minutes=30)

    # .order_by() clears model-level Meta.ordering so DISTINCT isn't defeated by timestamp
    services = list(
        LogEntry.objects.filter(timestamp__gte=window_start)
        .order_by()
        .values_list("service_name", flat=True)
        .distinct()
    )

    created_anomalies = []

    for service in services:
        # Build 6 five-minute buckets over the 30-minute window
        buckets = []
        for i in range(6):
            bucket_start = window_start + timedelta(minutes=i * 5)
            bucket_end = bucket_start + timedelta(minutes=5)
            count = LogEntry.objects.filter(
                service_name=service,
                timestamp__gte=bucket_start,
                timestamp__lt=bucket_end,
                level__in=["ERROR", "CRITICAL"],
            ).count()
            buckets.append(count)

        arr = np.array(buckets, dtype=float)
        std = arr.std()
        if std == 0:
            continue

        mean = arr.mean()
        z_scores = (arr - mean) / std  # z-score for every bucket
        peak_idx = int(np.argmax(z_scores))
        z_score = float(z_scores[peak_idx])

        if z_score < threshold:
            continue

        severity = _severity_from_z(z_score)
        error_count = int(arr[peak_idx])

        anomaly = AnomalyEvent.objects.create(
            service_name=service,
            severity=severity,
            z_score=round(z_score, 4),
            error_count=error_count,
            window_start=window_start + timedelta(minutes=peak_idx * 5),
            window_end=window_start + timedelta(minutes=(peak_idx + 1) * 5),
        )

        # Layer 2: compute and store health score
        health = compute_health_score(service)
        anomaly.health_score = health
        anomaly.save(update_fields=["health_score"])

        # Layer 3: LLM diagnosis
        _run_ai_diagnosis(anomaly, service)

        # Webhook
        _fire_webhooks(anomaly)

        created_anomalies.append(anomaly)

    # Take a health snapshot after detection
    take_health_snapshot()

    return created_anomalies


# ---------------------------------------------------------------------------
# Layer 2: Multi-signal health scoring (0–100)
# ---------------------------------------------------------------------------

def compute_health_score(service_name):
    from .models import LogEntry

    now = timezone.now()

    # Signal 1 — error rate last 60 mins (weight 50%)
    total_1h = LogEntry.objects.filter(
        service_name=service_name,
        timestamp__gte=now - timedelta(hours=1),
    ).count()
    errors_1h = LogEntry.objects.filter(
        service_name=service_name,
        timestamp__gte=now - timedelta(hours=1),
        level__in=["ERROR", "CRITICAL"],
    ).count()
    error_rate = (errors_1h / total_1h) if total_1h else 0
    signal_error = max(0.0, 1.0 - error_rate * 10)  # 10%+ error rate → 0

    # Signal 2 — avg response time vs baseline last 24h (weight 30%)
    from django.db.models import Avg
    baseline_rt = (
        LogEntry.objects.filter(
            service_name=service_name,
            timestamp__gte=now - timedelta(hours=24),
            response_time_ms__isnull=False,
        ).aggregate(avg=Avg("response_time_ms"))["avg"]
        or 0
    )
    recent_rt = (
        LogEntry.objects.filter(
            service_name=service_name,
            timestamp__gte=now - timedelta(minutes=10),
            response_time_ms__isnull=False,
        ).aggregate(avg=Avg("response_time_ms"))["avg"]
        or 0
    )
    if baseline_rt and recent_rt:
        ratio = recent_rt / baseline_rt
        signal_rt = max(0.0, 1.0 - max(0, ratio - 1.0))
    else:
        signal_rt = 1.0

    # Signal 3 — request volume drop >50% (weight 20%)
    vol_1h = total_1h
    vol_prev_1h = LogEntry.objects.filter(
        service_name=service_name,
        timestamp__gte=now - timedelta(hours=2),
        timestamp__lt=now - timedelta(hours=1),
    ).count()
    if vol_prev_1h:
        drop = (vol_prev_1h - vol_1h) / vol_prev_1h
        signal_vol = 0.0 if drop > 0.5 else 1.0
    else:
        signal_vol = 1.0

    score = (signal_error * 50) + (signal_rt * 30) + (signal_vol * 20)
    return round(score, 1)


def get_all_health_scores(since=None):
    from .models import LogEntry

    qs = LogEntry.objects.order_by()
    if since:
        qs = qs.filter(timestamp__gte=since)
    services = list(qs.values_list("service_name", flat=True).distinct())
    return {s: compute_health_score(s) for s in services}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_ai_diagnosis(anomaly, service_name):
    from .ai_diagnosis import get_ai_diagnosis
    from .models import LogEntry

    recent_logs = list(
        LogEntry.objects.filter(service_name=service_name).order_by("-timestamp")[:50]
    )
    try:
        get_ai_diagnosis(anomaly, recent_logs)
    except Exception as exc:
        logger.warning("AI diagnosis failed for anomaly %s: %s", anomaly.pk, exc)


def _build_webhook_payload(anomaly):
    score_now = anomaly.health_score or 0.0
    score_1h = _health_score_1h_ago(anomaly.service_name)
    change = score_now - score_1h
    if change > 5:
        trend = "improving"
    elif change < -5:
        trend = "degrading"
    else:
        trend = "stable"

    return {
        "event": "anomaly.detected",
        "timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "watchdog_version": "0.1.0",
        "anomaly": {
            "id": anomaly.pk,
            "service": anomaly.service_name,
            "severity": anomaly.severity,
            "z_score": anomaly.z_score,
            "error_count": anomaly.error_count,
            "window_start": anomaly.window_start.isoformat(),
            "window_end": anomaly.window_end.isoformat(),
            "ai_diagnosis": anomaly.ai_diagnosis or "",
        },
        "health": {
            "score_before": score_1h,
            "score_after": score_now,
            "trend": trend,
        },
        "action_required": True,
        "dashboard_url": "/watchdog/dashboard/",
    }


def _health_score_1h_ago(service_name):
    from .models import HealthSnapshot
    snap = (
        HealthSnapshot.objects.filter(service_name=service_name)
        .order_by("-recorded_at")
        .first()
    )
    return snap.health_score if snap else compute_health_score(service_name)


def _sign_payload(payload_bytes, secret):
    return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()  # noqa: S324


def _fire_webhooks(anomaly):
    from .models import WebhookConfig, WebhookEvent

    configs = list(WebhookConfig.objects.filter(is_active=True))
    if not configs:
        return

    payload = _build_webhook_payload(anomaly)
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    any_triggered = False

    for config in configs:
        signature = _sign_payload(payload_bytes, config.secret_token) if config.secret_token else ""
        headers = {
            "Content-Type": "application/json",
            "X-Watchdog-Event": "anomaly.detected",
            "X-Watchdog-Severity": anomaly.severity,
        }
        if signature:
            headers["X-Watchdog-Signature"] = f"sha256={signature}"

        success = False
        response_status = None
        response_body = ""
        error_message = ""

        try:
            resp = requests.post(
                config.url,
                data=payload_bytes,
                headers=headers,
                timeout=5,
            )
            response_status = resp.status_code
            response_body = resp.text[:2000]
            success = 200 <= resp.status_code < 300
            if not success:
                error_message = f"HTTP {resp.status_code}"
        except requests.Timeout:
            error_message = "Timeout after 5s"
        except Exception as exc:
            error_message = str(exc)[:500]

        WebhookEvent.objects.create(
            anomaly=anomaly,
            webhook_config=config,
            payload=payload,
            response_status=response_status,
            response_body=response_body,
            success=success,
            error_message=error_message,
        )
        if success:
            any_triggered = True
        logger.info(
            "Webhook delivery to %s: success=%s status=%s err=%s",
            config.url, success, response_status, error_message,
        )

    if any_triggered:
        anomaly.webhook_triggered = True
        anomaly.save(update_fields=["webhook_triggered"])


def take_health_snapshot():
    from .models import AnomalyEvent, HealthSnapshot, LogEntry

    now = timezone.now()
    since = now - timedelta(hours=1)

    services = list(
        LogEntry.objects.filter(timestamp__gte=since)
        .order_by()
        .values_list("service_name", flat=True)
        .distinct()
    )

    for service in services:
        total = LogEntry.objects.filter(service_name=service, timestamp__gte=since).count()
        errors = LogEntry.objects.filter(
            service_name=service, timestamp__gte=since, level__in=["ERROR", "CRITICAL"]
        ).count()
        error_rate = round((errors / total * 100) if total else 0, 2)
        health = compute_health_score(service)
        anomaly_count = AnomalyEvent.objects.filter(
            service_name=service, resolved=False, detected_at__gte=since
        ).count()
        HealthSnapshot.objects.create(
            service_name=service,
            health_score=health,
            error_rate=error_rate,
            request_count=total,
            anomaly_count=anomaly_count,
        )
