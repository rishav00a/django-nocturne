import json
import logging
from datetime import timedelta

from django.conf import settings as django_settings
from django.db.models import Avg, Count
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .detection import get_all_health_scores, run_detection, take_health_snapshot
from .models import AnomalyEvent, HealthSnapshot, LogEntry, WebhookConfig, WebhookEvent
from .permissions import NocturneAdminPermission, NocturneViewPermission
from .serializers import (
    AnomalyEventSerializer, AnomalyResolveSerializer,
    HealthSnapshotSerializer, LogEntryDetailSerializer, LogEntrySerializer,
    WebhookConfigSerializer, WebhookEventSerializer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeframe helpers
# ---------------------------------------------------------------------------

_TIMEFRAME_MINUTES = {
    "15m": 15, "30m": 30, "1h": 60, "3h": 180,
    "6h": 360, "12h": 720, "24h": 1440, "7d": 10080,
}


def _parse_timeframe(request):
    tf = request.query_params.get("timeframe", "1h").lower()
    return tf, _TIMEFRAME_MINUTES.get(tf, 60)


def _bucket_minutes(tf_minutes):
    if tf_minutes <= 60:    return 5
    if tf_minutes <= 360:   return 15
    if tf_minutes <= 1440:  return 30
    return 120


# ---------------------------------------------------------------------------
# Tier 2 — read-only endpoints (superuser OR view_nocturne)
# ---------------------------------------------------------------------------

class HealthView(APIView):
    permission_classes = [NocturneViewPermission]

    def get(self, request):
        tf, tf_minutes = _parse_timeframe(request)
        now = timezone.now()
        since = now - timedelta(minutes=tf_minutes)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_logs = LogEntry.objects.filter(timestamp__gte=since).count()
        total_tf = total_logs
        errors_tf = LogEntry.objects.filter(
            timestamp__gte=since, level__in=["ERROR", "CRITICAL"]
        ).count()
        error_rate = round((errors_tf / total_tf * 100) if total_tf else 0, 2)
        active_anomalies = AnomalyEvent.objects.filter(
            resolved=False, detected_at__gte=since
        ).count()
        resolved_today = AnomalyEvent.objects.filter(
            resolved=True, detected_at__gte=today_start
        ).count()

        return Response(
            {
                "total_logs": total_logs,
                "error_rate": error_rate,
                "active_anomalies": active_anomalies,
                "resolved_today": resolved_today,
                "service_health_scores": get_all_health_scores(since=since),
                "timeframe": tf,
            }
        )


class LogListView(APIView):
    permission_classes = [NocturneViewPermission]

    def get(self, request):
        qs = LogEntry.objects.all()
        service = request.query_params.get("service")
        level = request.query_params.get("level")
        since_param = request.query_params.get("since")
        search = request.query_params.get("search")
        tf_param = request.query_params.get("timeframe")

        if service:
            qs = qs.filter(service_name=service)
        if level:
            qs = qs.filter(level=level.upper())

        if tf_param:
            tf_minutes = _TIMEFRAME_MINUTES.get(tf_param.lower(), 60)
            since_dt = timezone.now() - timedelta(minutes=tf_minutes)
            qs = qs.filter(timestamp__gte=since_dt)
        elif since_param:
            try:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(since_param)
                if dt:
                    qs = qs.filter(timestamp__gte=dt)
            except Exception:
                pass

        if search:
            qs = qs.filter(message__icontains=search)

        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        try:
            page_size = int(request.query_params.get("page_size", 25))
            paginator.page_size = min(max(page_size, 1), 100)
        except (ValueError, TypeError):
            paginator.page_size = 25
        page = paginator.paginate_queryset(qs, request)
        serializer = LogEntrySerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class LogIngestView(APIView):
    permission_classes = [NocturneViewPermission]

    def post(self, request):
        serializer = LogEntryDetailSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AnomalyListView(APIView):
    permission_classes = [NocturneViewPermission]

    def get(self, request):
        qs = AnomalyEvent.objects.all()
        resolved = request.query_params.get("resolved")
        severity = request.query_params.get("severity")
        tf_param = request.query_params.get("timeframe")

        if resolved is not None:
            qs = qs.filter(resolved=resolved.lower() == "true")
        if severity:
            qs = qs.filter(severity=severity.upper())
        if tf_param:
            tf_minutes = _TIMEFRAME_MINUTES.get(tf_param.lower(), 60)
            since = timezone.now() - timedelta(minutes=tf_minutes)
            qs = qs.filter(detected_at__gte=since)

        serializer = AnomalyEventSerializer(qs[:100], many=True)
        return Response(serializer.data)


class DashboardDataView(APIView):
    permission_classes = [NocturneViewPermission]

    def get(self, request):
        tf, tf_minutes = _parse_timeframe(request)
        now = timezone.now()
        since = now - timedelta(minutes=tf_minutes)
        bucket_mins = _bucket_minutes(tf_minutes)
        n_buckets = tf_minutes // bucket_mins
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        services = list(
            LogEntry.objects.filter(timestamp__gte=since)
            .order_by()
            .values_list("service_name", flat=True)
            .distinct()
        )
        labels = []
        error_series = {s: [] for s in services}
        for i in range(n_buckets):
            bucket_start = since + timedelta(minutes=i * bucket_mins)
            bucket_end = bucket_start + timedelta(minutes=bucket_mins)
            labels.append(bucket_start.strftime("%H:%M"))
            for s in services:
                count = LogEntry.objects.filter(
                    service_name=s,
                    timestamp__gte=bucket_start,
                    timestamp__lt=bucket_end,
                    level__in=["ERROR", "CRITICAL"],
                ).count()
                error_series[s].append(count)

        health_scores = get_all_health_scores(since=since)

        level_dist = dict(
            LogEntry.objects.filter(timestamp__gte=since)
            .values("level")
            .annotate(count=Count("id"))
            .values_list("level", "count")
        )

        # Recent anomalies — always most-recent 10 (for intel bar / widget C)
        recent_anomalies = list(
            AnomalyEvent.objects.order_by("-detected_at")[:10].values(
                "id", "service_name", "severity", "z_score", "error_count",
                "health_score", "window_start", "window_end", "detected_at",
                "resolved", "ai_diagnosis", "ai_diagnosed_at", "webhook_triggered",
            )
        )
        for a in recent_anomalies:
            a["detected_at"] = a["detected_at"].isoformat()
            if a.get("window_start"):
                a["window_start"] = a["window_start"].isoformat()
            if a.get("window_end"):
                a["window_end"] = a["window_end"].isoformat()
            if a.get("ai_diagnosed_at"):
                a["ai_diagnosed_at"] = a["ai_diagnosed_at"].isoformat()

        apm = getattr(django_settings, "NOCTURNE", {})
        backend = apm.get("AI_BACKEND", "ollama")
        _model_keys = {
            "ollama":    ("OLLAMA_MODEL",    "llama3.2"),
            "anthropic": ("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            "openai":    ("OPENAI_MODEL",    "gpt-4o"),
            "gemini":    ("GEMINI_MODEL",    "gemini-1.5-flash"),
        }
        mk, md = _model_keys.get(backend, ("OLLAMA_MODEL", "llama3.2"))
        ai_model = apm.get(mk, md)

        active_anomalies = AnomalyEvent.objects.filter(
            resolved=False, detected_at__gte=since
        ).count()
        resolved_today = AnomalyEvent.objects.filter(
            resolved=True, detected_at__gte=today_start
        ).count()

        slowest_endpoints = list(
            LogEntry.objects.filter(
                timestamp__gte=since,
                response_time_ms__isnull=False,
            )
            .values("request_path")
            .annotate(avg_ms=Avg("response_time_ms"))
            .order_by("-avg_ms")[:5]
        )

        request_volume = []
        for i in range(n_buckets):
            bucket_start = since + timedelta(minutes=i * bucket_mins)
            bucket_end = bucket_start + timedelta(minutes=bucket_mins)
            vol_count = LogEntry.objects.filter(
                timestamp__gte=bucket_start,
                timestamp__lt=bucket_end,
            ).count()
            request_volume.append({"bucket": bucket_start.strftime("%H:%M"), "count": vol_count})

        health_trends = _build_health_trends(services)

        return Response(
            {
                "timeframe": tf,
                "bucket_minutes": bucket_mins,
                "labels": labels,
                "services": services,
                "error_series": error_series,
                "health_scores": health_scores,
                "level_distribution": level_dist,
                "recent_anomalies": recent_anomalies,
                "active_anomalies": active_anomalies,
                "resolved_today": resolved_today,
                "ai_backend_name": backend,
                "ai_model_name": ai_model,
                "slowest_endpoints": slowest_endpoints,
                "request_volume": request_volume,
                "health_trends": health_trends,
            }
        )


def _build_health_trends(services):
    from .detection import compute_health_score
    now = timezone.now()
    one_hour_ago = now - timedelta(hours=1)
    trends = {}
    for svc in services:
        snapshots = list(
            HealthSnapshot.objects.filter(service_name=svc)
            .order_by("-recorded_at")[:12]
        )
        current = compute_health_score(svc)
        # Find last snapshot older than 1h for comparison
        older = (
            HealthSnapshot.objects.filter(service_name=svc, recorded_at__lte=one_hour_ago)
            .order_by("-recorded_at")
            .first()
        )
        score_1h_ago = older.health_score if older else (snapshots[-1].health_score if snapshots else current)
        change = round(current - score_1h_ago, 1)
        if change > 5:
            trend = "improving"
        elif change < -5:
            trend = "degrading"
        else:
            trend = "stable"
        trends[svc] = {
            "current": current,
            "1h_ago": score_1h_ago,
            "trend": trend,
            "change": change,
            "snapshots": [
                {"time": s.recorded_at.strftime("%H:%M"), "score": s.health_score}
                for s in reversed(snapshots)
            ],
        }
    return trends


# ---------------------------------------------------------------------------
# Tier 1 — admin-only endpoints (superuser only)
# ---------------------------------------------------------------------------

class DetectView(APIView):
    permission_classes = [NocturneAdminPermission]

    def post(self, request):
        anomalies = run_detection()
        serializer = AnomalyEventSerializer(anomalies, many=True)
        return Response(
            {
                "anomalies_detected": len(anomalies),
                "anomalies": serializer.data,
            }
        )


class AnomalyDetailView(APIView):
    permission_classes = [NocturneAdminPermission]

    def patch(self, request, pk):
        try:
            anomaly = AnomalyEvent.objects.get(pk=pk)
        except AnomalyEvent.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AnomalyResolveSerializer(anomaly, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(AnomalyEventSerializer(anomaly).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogEntryDetailView(APIView):
    permission_classes = [NocturneViewPermission]

    def get(self, request, pk):
        try:
            log = LogEntry.objects.get(pk=pk)
        except LogEntry.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(LogEntryDetailSerializer(log).data)


class LogAnalysisView(APIView):
    permission_classes = [NocturneViewPermission]

    def post(self, request, pk):
        try:
            log = LogEntry.objects.get(pk=pk)
        except LogEntry.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        apm = getattr(django_settings, "NOCTURNE", {})
        backend = apm.get("AI_BACKEND", "ollama")
        _model_keys = {
            "ollama":    ("OLLAMA_MODEL",    "llama3.2"),
            "anthropic": ("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            "openai":    ("OPENAI_MODEL",    "gpt-4o"),
            "gemini":    ("GEMINI_MODEL",    "gemini-1.5-flash"),
        }
        mk, md = _model_keys.get(backend, ("OLLAMA_MODEL", "llama3.2"))
        model_name = apm.get(mk, md)

        if log.ai_analysis:
            return Response({
                "analysis": log.ai_analysis,
                "model": model_name,
                "cached": True,
                "ai_analysed_at": log.ai_analysed_at.isoformat() if log.ai_analysed_at else None,
            })

        from .ai_diagnosis import get_log_analysis
        context_before = list(
            LogEntry.objects.filter(
                service_name=log.service_name,
                timestamp__lt=log.timestamp,
            ).order_by("-timestamp")[:5]
        )[::-1]
        context_after = list(
            LogEntry.objects.filter(
                service_name=log.service_name,
                timestamp__gt=log.timestamp,
            ).order_by("timestamp")[:5]
        )
        analysis = get_log_analysis(log, context_before + context_after)
        log.ai_analysis = analysis
        log.ai_analysed_at = timezone.now()
        log.save(update_fields=["ai_analysis", "ai_analysed_at"])

        return Response({
            "analysis": analysis,
            "model": model_name,
            "cached": False,
            "ai_analysed_at": log.ai_analysed_at.isoformat(),
        })


class WebhookReceiveView(APIView):
    permission_classes = [NocturneAdminPermission]

    def post(self, request):
        import hashlib
        import hmac as hmac_mod

        data = request.data
        service = ""
        severity = ""
        event_type = data.get("event", "unknown")

        if "anomaly" in data and isinstance(data["anomaly"], dict):
            service = data["anomaly"].get("service", "")
            severity = data["anomaly"].get("severity", "")

        # Validate signature if secret configured
        sig_header = request.META.get("HTTP_X_WATCHDOG_SIGNATURE", "")
        if sig_header.startswith("sha256="):
            apm = getattr(django_settings, "NOCTURNE", {})
            secret = apm.get("WEBHOOK_SECRET", "")
            if secret:
                body = request.body
                expected = "sha256=" + hmac_mod.new(
                    secret.encode(), body, hashlib.sha256
                ).hexdigest()
                if not hmac_mod.compare_digest(sig_header, expected):
                    logger.warning("Webhook signature mismatch")
                    return Response({"detail": "Invalid signature."}, status=status.HTTP_403_FORBIDDEN)

        logger.info("WEBHOOK RECEIVED: %s anomaly on %s", severity or "unknown", service or "unknown")

        return Response({
            "status": "received",
            "event": event_type,
            "service": service,
            "severity": severity,
            "received_at": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message": "Watchdog alert received and acknowledged",
        })


class WebhookConfigView(APIView):
    """GET /api/webhooks/  POST /api/webhooks/"""
    permission_classes = [NocturneAdminPermission]

    def get(self, request):
        configs = WebhookConfig.objects.all()
        return Response(WebhookConfigSerializer(configs, many=True).data)

    def post(self, request):
        ser = WebhookConfigSerializer(data=request.data)
        if ser.is_valid():
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)


class WebhookConfigDetailView(APIView):
    """PUT/DELETE /api/webhooks/{id}/"""
    permission_classes = [NocturneAdminPermission]

    def _get(self, pk):
        try:
            return WebhookConfig.objects.get(pk=pk)
        except WebhookConfig.DoesNotExist:
            return None

    def put(self, request, pk):
        obj = self._get(pk)
        if obj is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        ser = WebhookConfigSerializer(obj, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = self._get(pk)
        if obj is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookEventListView(APIView):
    """GET /api/webhooks/events/"""
    permission_classes = [NocturneViewPermission]

    def get(self, request):
        limit = min(int(request.query_params.get("limit", 20)), 100)
        events = WebhookEvent.objects.select_related("anomaly", "webhook_config")[:limit]
        return Response(WebhookEventSerializer(events, many=True).data)


class WebhookTestView(APIView):
    """POST /api/webhooks/test/  — send a test ping to all active configs"""
    permission_classes = [NocturneAdminPermission]

    def post(self, request):
        import hashlib
        import hmac as hmac_mod

        configs = list(WebhookConfig.objects.filter(is_active=True))
        if not configs:
            return Response({"detail": "No active webhook configurations."}, status=status.HTTP_400_BAD_REQUEST)

        test_payload = {
            "event": "watchdog.test",
            "timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "watchdog_version": "0.1.0",
            "message": "This is a test webhook from Nocturne.",
        }
        payload_bytes = json.dumps(test_payload, separators=(",", ":")).encode()

        results = []
        for config in configs:
            signature = ""
            if config.secret_token:
                signature = "sha256=" + hmac_mod.new(
                    config.secret_token.encode(), payload_bytes, hashlib.sha256
                ).hexdigest()
            headers = {
                "Content-Type": "application/json",
                "X-Watchdog-Event": "watchdog.test",
                "X-Watchdog-Severity": "LOW",
            }
            if signature:
                headers["X-Watchdog-Signature"] = signature

            success = False
            response_status = None
            error_message = ""
            try:
                import requests as req_lib
                resp = req_lib.post(config.url, data=payload_bytes, headers=headers, timeout=5)
                response_status = resp.status_code
                success = 200 <= resp.status_code < 300
                if not success:
                    error_message = f"HTTP {resp.status_code}"
            except Exception as exc:
                error_message = str(exc)[:500]

            WebhookEvent.objects.create(
                anomaly=None,
                webhook_config=config,
                payload=test_payload,
                response_status=response_status,
                success=success,
                error_message=error_message,
            )
            results.append({"url": config.url, "success": success, "error": error_message})

        overall = all(r["success"] for r in results)
        return Response({"success": overall, "results": results})


# ---------------------------------------------------------------------------
# Standalone dashboard — browser view
# ---------------------------------------------------------------------------

def _get_login_url():
    return getattr(django_settings, "NOCTURNE", {}).get("LOGIN_URL", "/admin/login/")


def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect(f"{_get_login_url()}?next={request.path}")
    if not (request.user.is_superuser or request.user.has_perm("nocturne.view_nocturne")):
        return HttpResponseForbidden(
            render_to_string("nocturne/403.html", request=request)
        )
    return render(request, "nocturne/dashboard.html")
