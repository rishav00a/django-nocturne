import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


SERVICES = [
    "auth-service",
    "payment-service",
    "api-gateway",
    "notification-service",
    "user-service",
]

PATHS = [
    "/api/v1/login",
    "/api/v1/logout",
    "/api/v1/token/refresh",
    "/api/v1/payment",
    "/api/v1/charge",
    "/api/v1/refund",
    "/api/v1/users",
    "/api/v1/profile",
    "/api/v1/notify",
    "/api/v1/health",
    "/api/v1/orders",
    "/api/v1/products",
]

MESSAGES_OK = [
    "Request processed successfully",
    "User authenticated",
    "Cache hit",
    "Query executed in 12ms",
    "Response served from cache",
]

# Realistic fake stacktraces for random ERROR logs outside spikes
RANDOM_ERRORS = [
    {
        "exception_type": "ValueError",
        "exception_message": "Invalid input data: expected int got str",
        "stacktrace": (
            "Traceback (most recent call last):\n"
            '  File "/app/api/views.py", line 88, in handle_request\n'
            "    validated = self.validate_payload(request.data)\n"
            '  File "/app/api/validators.py", line 23, in validate_field\n'
            "    return int(value)\n"
            "ValueError: Invalid input data: expected int got str"
        ),
    },
    {
        "exception_type": "KeyError",
        "exception_message": "Missing required field: 'user_id'",
        "stacktrace": (
            "Traceback (most recent call last):\n"
            '  File "/app/api/views.py", line 142, in post\n'
            "    serialized = self.serializer_class(data=request.data)\n"
            '  File "/app/api/serializers.py", line 67, in to_internal_value\n'
            "    user_id = data['user_id']\n"
            "KeyError: Missing required field: 'user_id'"
        ),
    },
    {
        "exception_type": "TimeoutError",
        "exception_message": "Redis cache timeout after 3000ms",
        "stacktrace": (
            "Traceback (most recent call last):\n"
            '  File "/app/api/views.py", line 56, in get\n'
            "    data = self.cache.get_or_compute(key, compute_fn)\n"
            '  File "/app/core/cache.py", line 89, in get_cached\n'
            "    result = redis_client.get(key, timeout=3.0)\n"
            "TimeoutError: Redis cache timeout after 3000ms"
        ),
    },
    {
        "exception_type": "PermissionError",
        "exception_message": "Insufficient privileges for resource /admin/users",
        "stacktrace": (
            "Traceback (most recent call last):\n"
            '  File "/app/api/views.py", line 201, in dispatch\n'
            "    self.check_permissions(request)\n"
            '  File "/app/auth/permissions.py", line 45, in check_permission\n'
            '    raise PermissionError(f"Insufficient privileges for resource {resource}")\n'
            "PermissionError: Insufficient privileges for resource /admin/users"
        ),
    },
]

SPIKE1_STACKTRACE = (
    "Traceback (most recent call last):\n"
    '  File "/app/services/payment/processor.py", line 87, in process_payment\n'
    "    conn = db_pool.get_connection(timeout=30)\n"
    '  File "/app/core/database/pool.py", line 134, in get_connection\n'
    '    raise DatabaseConnectionError(f"Pool exhausted after {timeout}s")\n'
    "DatabaseConnectionError: Connection pool exhausted after 30s timeout"
)

SPIKE2_STACKTRACE = (
    "Traceback (most recent call last):\n"
    '  File "/app/gateway/proxy.py", line 203, in forward_request\n'
    "    response = await upstream.send(request, timeout=5.0)\n"
    '  File "/app/gateway/upstream.py", line 67, in send\n'
    '    raise UpstreamTimeoutError(f"No response within {timeout*1000:.0f}ms")\n'
    "UpstreamTimeoutError: Upstream service did not respond within 5000ms"
)

SPIKE3_STACKTRACE = (
    "Traceback (most recent call last):\n"
    '  File "/app/auth/middleware.py", line 45, in validate_token\n'
    '    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])\n'
    '  File "/app/auth/jwt_utils.py", line 92, in decode\n'
    '    raise TokenValidationError("JWT signature verification failed: token expired")\n'
    "TokenValidationError: JWT signature verification failed: token expired"
)


class Command(BaseCommand):
    help = "Generate 1000 demo log entries with 3 error spikes for testing Nocturne"

    def handle(self, *args, **options):
        from nocturne.models import (
            AnomalyEvent, HealthSnapshot, LogEntry, WebhookConfig, WebhookEvent,
        )
        from nocturne.detection import run_detection, take_health_snapshot

        self.stdout.write("Clearing existing data…")
        WebhookEvent.objects.all().delete()
        HealthSnapshot.objects.all().delete()
        AnomalyEvent.objects.all().delete()
        LogEntry.objects.all().delete()

        now = timezone.now()
        entries = []

        self.stdout.write("Generating baseline traffic (850 entries)…")
        for _ in range(850):
            service = random.choice(SERVICES)
            offset_mins = random.randint(1, 120)
            ts = now - timedelta(minutes=offset_mins, seconds=random.randint(0, 59))
            http_status = random.choices([200, 201, 204, 400, 404, 500], weights=[70, 5, 5, 8, 7, 5])[0]
            level = "ERROR" if http_status >= 500 else ("WARNING" if http_status >= 400 else "INFO")

            err = random.choice(RANDOM_ERRORS) if level == "ERROR" else {}
            entries.append(LogEntry(
                service_name=service,
                timestamp=ts,
                level=level,
                message=err.get("exception_message") or (
                    random.choice(MESSAGES_OK) if level == "INFO"
                    else f"HTTP {http_status} error on {random.choice(PATHS)}"
                ),
                request_path=random.choice(PATHS),
                response_time_ms=round(random.uniform(10, 400), 1),
                status_code=http_status,
                source_ip=f"10.0.{random.randint(0, 255)}.{random.randint(1, 254)}",
                exception_type=err.get("exception_type"),
                exception_message=err.get("exception_message"),
                stacktrace=err.get("stacktrace"),
            ))

        # Spike 1 — payment-service, 45 mins ago, 35 ERROR entries in 2 minutes
        self.stdout.write("Injecting spike 1: payment-service @ 45 mins ago…")
        spike1_base = now - timedelta(minutes=45)
        for _ in range(35):
            entries.append(LogEntry(
                service_name="payment-service",
                timestamp=spike1_base + timedelta(seconds=random.randint(0, 120)),
                level="ERROR",
                message="Connection pool exhausted after 30s timeout",
                request_path="/api/v1/payment",
                response_time_ms=round(random.uniform(800, 3000), 1),
                status_code=500,
                source_ip="10.0.1.100",
                exception_type="DatabaseConnectionError",
                exception_message="Connection pool exhausted after 30s timeout",
                stacktrace=SPIKE1_STACKTRACE,
            ))

        # Spike 2 — api-gateway, 20 mins ago, 40 CRITICAL entries in 2 minutes
        self.stdout.write("Injecting spike 2: api-gateway @ 20 mins ago…")
        spike2_base = now - timedelta(minutes=20)
        for _ in range(40):
            entries.append(LogEntry(
                service_name="api-gateway",
                timestamp=spike2_base + timedelta(seconds=random.randint(0, 120)),
                level="CRITICAL",
                message="Upstream service did not respond within 5000ms",
                request_path="/api/v1/orders",
                response_time_ms=round(random.uniform(5000, 15000), 1),
                status_code=503,
                source_ip="10.0.2.50",
                exception_type="UpstreamTimeoutError",
                exception_message="Upstream service did not respond within 5000ms",
                stacktrace=SPIKE2_STACKTRACE,
            ))

        # Spike 3 — auth-service, 5 mins ago, 50 ERROR entries in 90 seconds
        self.stdout.write("Injecting spike 3: auth-service @ 5 mins ago…")
        spike3_base = now - timedelta(minutes=5)
        for _ in range(50):
            entries.append(LogEntry(
                service_name="auth-service",
                timestamp=spike3_base + timedelta(seconds=random.randint(0, 90)),
                level="ERROR",
                message="JWT signature verification failed: token expired",
                request_path="/api/v1/token/refresh",
                response_time_ms=round(random.uniform(200, 1200), 1),
                status_code=401,
                source_ip=f"10.0.0.{random.randint(1, 254)}",
                exception_type="TokenValidationError",
                exception_message="JWT signature verification failed: token expired",
                stacktrace=SPIKE3_STACKTRACE,
            ))

        # Capture timestamps BEFORE bulk_create (auto_now_add overwrites in-place)
        intended_timestamps = [e.timestamp for e in entries]
        self.stdout.write(f"Bulk inserting {len(entries)} log entries…")
        created = LogEntry.objects.bulk_create(entries, batch_size=200)
        self.stdout.write("Fixing timestamps via raw SQL (auto_now_add bypass)…")
        table = LogEntry._meta.db_table
        with connection.cursor() as cursor:
            cursor.executemany(
                f"UPDATE {table} SET timestamp = %s WHERE id = %s",
                [(ts.isoformat(sep=" "), obj.id) for ts, obj in zip(intended_timestamps, created)],
            )

        total = LogEntry.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Inserted {total} log entries."))

        self.stdout.write("Running detection pipeline…")
        anomalies = run_detection()
        self.stdout.write(self.style.SUCCESS(
            f"Detection complete — {len(anomalies)} anomalies created with AI diagnosis."
        ))

        # Ensure a simulated webhook receiver is configured
        self.stdout.write("Seeding WebhookConfig (simulated receiver)…")
        wh_config, _ = WebhookConfig.objects.get_or_create(
            name="Simulated Receiver",
            defaults={
                "url": "http://127.0.0.1:8000/watchdog/api/webhook/receive/",
                "is_active": True,
                "secret_token": "demo-secret-token",
            },
        )

        # Seed historical WebhookEvents for the demo (past deliveries)
        self.stdout.write("Seeding demo WebhookEvents…")
        WebhookEvent.objects.filter(webhook_config=wh_config, anomaly__isnull=True).delete()
        demo_events = []
        anomaly_list = list(AnomalyEvent.objects.all())
        for i, a in enumerate(anomaly_list[:3]):
            # 2 successes, 1 failure for variety
            success = (i != 1)
            payload = {
                "event": "anomaly.detected",
                "timestamp": a.detected_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "watchdog_version": "0.1.0",
                "anomaly": {
                    "id": a.pk,
                    "service": a.service_name,
                    "severity": a.severity,
                    "z_score": a.z_score,
                },
            }
            demo_events.append(WebhookEvent(
                anomaly=a,
                webhook_config=wh_config,
                payload=payload,
                response_status=200 if success else None,
                response_body='{"status":"received"}' if success else "",
                success=success,
                error_message="" if success else "Connection refused: 127.0.0.1:9999",
            ))
        WebhookEvent.objects.bulk_create(demo_events)
        wh_ts = [now - timedelta(minutes=45 - i * 15) for i in range(len(demo_events))]
        wh_table = WebhookEvent._meta.db_table
        created_wh = list(WebhookEvent.objects.order_by("-id")[:len(demo_events)])
        with connection.cursor() as cursor:
            cursor.executemany(
                f"UPDATE {wh_table} SET triggered_at = %s WHERE id = %s",
                [(ts.isoformat(sep=" "), obj.id) for ts, obj in zip(wh_ts, reversed(created_wh))],
            )
        self.stdout.write(self.style.SUCCESS(f"Created {len(demo_events)} demo WebhookEvents."))

        # Seed historical HealthSnapshots (one per 10 mins over last 2h)
        self.stdout.write("Seeding HealthSnapshots…")
        HealthSnapshot.objects.all().delete()
        snap_entries = []
        import random as _rnd
        for service in SERVICES:
            for j in range(13):
                offset = timedelta(minutes=j * 10)
                snap_time = now - timedelta(hours=2) + offset
                # Degrade auth-service over time to show trend
                if service == "auth-service":
                    score = max(10.0, 85.0 - j * 5)
                elif service == "payment-service":
                    score = max(15.0, 90.0 - j * 4)
                else:
                    score = _rnd.uniform(70, 95)
                snap_entries.append(HealthSnapshot(
                    service_name=service,
                    health_score=round(score, 1),
                    error_rate=round(max(0, (100 - score) / 5), 2),
                    request_count=_rnd.randint(50, 300),
                    anomaly_count=1 if score < 40 else 0,
                ))
        created_snaps = HealthSnapshot.objects.bulk_create(snap_entries)
        snap_table = HealthSnapshot._meta.db_table
        snap_times = []
        for service in SERVICES:
            for j in range(13):
                snap_times.append(now - timedelta(hours=2) + timedelta(minutes=j * 10))
        with connection.cursor() as cursor:
            cursor.executemany(
                f"UPDATE {snap_table} SET recorded_at = %s WHERE id = %s",
                [(ts.isoformat(sep=" "), obj.id) for ts, obj in zip(snap_times, created_snaps)],
            )
        self.stdout.write(self.style.SUCCESS(f"Created {len(created_snaps)} HealthSnapshots."))
        self.stdout.write(self.style.SUCCESS("Demo data generation complete."))
