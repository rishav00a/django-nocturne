from rest_framework import serializers

from .models import AnomalyEvent, HealthSnapshot, LogEntry, WebhookConfig, WebhookEvent


class LogEntrySerializer(serializers.ModelSerializer):
    """Light serializer for list responses — excludes heavy stacktrace field."""
    class Meta:
        model = LogEntry
        fields = [
            "id", "timestamp", "service_name", "level", "message",
            "exception_type", "exception_message",
            "request_path", "status_code", "response_time_ms", "source_ip",
            "ai_analysis", "ai_analysed_at",
        ]
        read_only_fields = ["id", "timestamp"]


class LogEntryDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail view and ingest — includes stacktrace."""
    class Meta:
        model = LogEntry
        fields = "__all__"
        read_only_fields = ["id", "timestamp"]


class AnomalyEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyEvent
        fields = "__all__"
        read_only_fields = ["id", "detected_at"]


class AnomalyResolveSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyEvent
        fields = ["resolved"]


class WebhookConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookConfig
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class WebhookEventSerializer(serializers.ModelSerializer):
    service_name = serializers.SerializerMethodField()
    severity = serializers.SerializerMethodField()
    webhook_url = serializers.SerializerMethodField()

    class Meta:
        model = WebhookEvent
        fields = [
            "id", "triggered_at", "anomaly", "webhook_config",
            "payload", "response_status", "response_body",
            "success", "error_message",
            "service_name", "severity", "webhook_url",
        ]
        read_only_fields = ["id", "triggered_at"]

    def get_service_name(self, obj):
        return obj.anomaly.service_name if obj.anomaly else None

    def get_severity(self, obj):
        return obj.anomaly.severity if obj.anomaly else None

    def get_webhook_url(self, obj):
        return obj.webhook_config.url if obj.webhook_config else None


class HealthSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthSnapshot
        fields = "__all__"
        read_only_fields = ["id", "recorded_at"]
