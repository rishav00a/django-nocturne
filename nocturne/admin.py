from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html

from .models import AnomalyEvent, HealthSnapshot, LogEntry, WebhookConfig, WebhookEvent


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "service_name", "level_badge", "request_path", "status_code", "response_time_ms"]
    list_filter = ["level", "service_name", "timestamp"]
    search_fields = ["message", "request_path", "source_ip"]
    readonly_fields = ["timestamp"]
    ordering = ["-timestamp"]

    def level_badge(self, obj):
        colors = {"INFO": "#17a2b8", "WARNING": "#ffc107", "ERROR": "#dc3545", "CRITICAL": "#6f42c1"}
        color = colors.get(obj.level, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>',
            color, obj.level,
        )
    level_badge.short_description = "Level"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["dashboard_url"] = "/admin/nocturne/dashboard/"
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(AnomalyEvent)
class AnomalyEventAdmin(admin.ModelAdmin):
    list_display = ["detected_at", "service_name", "severity_badge", "z_score", "error_count", "health_score", "resolved", "has_diagnosis"]
    list_filter = ["severity", "resolved", "service_name"]
    readonly_fields = ["detected_at", "ai_diagnosed_at", "ai_diagnosis"]
    ordering = ["-detected_at"]
    actions = ["mark_resolved"]

    def severity_badge(self, obj):
        colors = {"LOW": "#28a745", "MEDIUM": "#ffc107", "HIGH": "#fd7e14", "CRITICAL": "#dc3545"}
        color = colors.get(obj.severity, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>',
            color, obj.severity,
        )
    severity_badge.short_description = "Severity"

    def has_diagnosis(self, obj):
        return bool(obj.ai_diagnosis)
    has_diagnosis.boolean = True
    has_diagnosis.short_description = "AI Diagnosis"

    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True)
    mark_resolved.short_description = "Mark selected anomalies as resolved"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["dashboard_url"] = "/admin/nocturne/dashboard/"
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(WebhookConfig)
class WebhookConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "is_active", "created_at"]
    list_filter = ["is_active"]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ["triggered_at", "anomaly", "webhook_config", "success", "response_status"]
    list_filter = ["success"]
    readonly_fields = ["triggered_at", "payload", "response_body"]
    ordering = ["-triggered_at"]


@admin.register(HealthSnapshot)
class HealthSnapshotAdmin(admin.ModelAdmin):
    list_display = ["recorded_at", "service_name", "health_score", "error_rate", "request_count"]
    list_filter = ["service_name"]
    readonly_fields = ["recorded_at"]
    ordering = ["-recorded_at"]


def _admin_dashboard_view(request):
    """Custom admin dashboard — requires superuser or view_nocturne permission."""
    if not (request.user.is_superuser or request.user.has_perm("nocturne.view_nocturne")):
        raise PermissionDenied
    return render(request, "nocturne/admin_dashboard.html", {"title": "Nocturne Dashboard"})


# Monkey-patch the default admin site to inject the dashboard URL.
# admin_view() wraps the view with is_active + is_staff checks; our explicit
# PermissionDenied check inside adds the finer-grained tier check on top.
_original_get_urls = admin.site.__class__.get_urls


def _patched_get_urls(self):
    from django.urls import path as dpath
    urls = _original_get_urls(self)
    extra = [
        dpath(
            "nocturne/dashboard/",
            self.admin_view(_admin_dashboard_view),
            name="nocturne_dashboard",
        )
    ]
    return extra + urls


admin.site.__class__.get_urls = _patched_get_urls
