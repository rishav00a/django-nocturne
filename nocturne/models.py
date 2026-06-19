from django.db import models


class LogEntry(models.Model):
    LEVEL_CHOICES = [
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    service_name = models.CharField(max_length=128, db_index=True, default="default")
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default="INFO", db_index=True)
    message = models.TextField(blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    request_path = models.CharField(max_length=512, blank=True)
    response_time_ms = models.FloatField(null=True, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    stacktrace = models.TextField(blank=True, null=True)
    exception_type = models.CharField(max_length=255, blank=True, null=True)
    exception_message = models.CharField(max_length=1000, blank=True, null=True)
    ai_analysis = models.TextField(blank=True, null=True)
    ai_analysed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Log Entry"
        verbose_name_plural = "Log Entries"
        permissions = [("view_nocturne", "Can view Nocturne")]

    def __str__(self):
        return f"[{self.level}] {self.service_name} {self.request_path} @ {self.timestamp:%Y-%m-%d %H:%M:%S}"


class AnomalyEvent(models.Model):
    SEVERITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    service_name = models.CharField(max_length=128, db_index=True)
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="MEDIUM")
    z_score = models.FloatField()
    error_count = models.PositiveIntegerField(default=0)
    health_score = models.FloatField(null=True, blank=True)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    webhook_triggered = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False, db_index=True)
    ai_diagnosis = models.TextField(blank=True)
    ai_diagnosed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at"]
        verbose_name = "Anomaly Event"
        verbose_name_plural = "Anomaly Events"

    def __str__(self):
        return f"[{self.severity}] {self.service_name} z={self.z_score:.2f} @ {self.detected_at:%Y-%m-%d %H:%M:%S}"


class WebhookConfig(models.Model):
    name = models.CharField(max_length=128)
    url = models.URLField()
    is_active = models.BooleanField(default=True)
    secret_token = models.CharField(max_length=256, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Webhook Config"
        verbose_name_plural = "Webhook Configs"

    def __str__(self):
        return f"{self.name} → {self.url}"


class WebhookEvent(models.Model):
    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    anomaly = models.ForeignKey(
        AnomalyEvent, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="webhook_events",
    )
    webhook_config = models.ForeignKey(
        WebhookConfig, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="events",
    )
    payload = models.JSONField(default=dict)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-triggered_at"]
        verbose_name = "Webhook Event"
        verbose_name_plural = "Webhook Events"

    def __str__(self):
        status = "✓" if self.success else "✗"
        svc = self.anomaly.service_name if self.anomaly else "test"
        return f"[{status}] {svc} @ {self.triggered_at:%Y-%m-%d %H:%M:%S}"


class HealthSnapshot(models.Model):
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    service_name = models.CharField(max_length=128, db_index=True)
    health_score = models.FloatField()
    error_rate = models.FloatField()
    request_count = models.IntegerField()
    anomaly_count = models.IntegerField()

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "Health Snapshot"
        verbose_name_plural = "Health Snapshots"
        indexes = [models.Index(fields=["service_name", "recorded_at"])]

    def __str__(self):
        return f"{self.service_name} score={self.health_score} @ {self.recorded_at:%Y-%m-%d %H:%M:%S}"
