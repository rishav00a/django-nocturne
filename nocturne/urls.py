from django.urls import path

from .views import (
    AnomalyDetailView,
    AnomalyListView,
    DashboardDataView,
    DetectView,
    HealthView,
    LogAnalysisView,
    LogEntryDetailView,
    LogIngestView,
    LogListView,
    WebhookConfigDetailView,
    WebhookConfigView,
    WebhookEventListView,
    WebhookReceiveView,
    WebhookTestView,
    dashboard_view,
)

urlpatterns = [
    path("dashboard/", dashboard_view, name="nocturne-dashboard"),
    path("api/health/", HealthView.as_view(), name="nocturne-health"),
    path("api/logs/", LogListView.as_view(), name="nocturne-logs"),
    path("api/logs/ingest/", LogIngestView.as_view(), name="nocturne-logs-ingest"),
    path("api/logs/<int:pk>/", LogEntryDetailView.as_view(), name="nocturne-log-detail"),
    path("api/logs/<int:pk>/analyse/", LogAnalysisView.as_view(), name="nocturne-log-analyse"),
    path("api/detect/", DetectView.as_view(), name="nocturne-detect"),
    path("api/anomalies/", AnomalyListView.as_view(), name="nocturne-anomalies"),
    path("api/anomalies/<int:pk>/", AnomalyDetailView.as_view(), name="nocturne-anomaly-detail"),
    path("api/webhook/receive/", WebhookReceiveView.as_view(), name="nocturne-webhook-receive"),
    path("api/webhooks/", WebhookConfigView.as_view(), name="nocturne-webhooks"),
    path("api/webhooks/events/", WebhookEventListView.as_view(), name="nocturne-webhook-events"),
    path("api/webhooks/test/", WebhookTestView.as_view(), name="nocturne-webhook-test"),
    path("api/webhooks/<int:pk>/", WebhookConfigDetailView.as_view(), name="nocturne-webhook-detail"),
    path("api/dashboard/data/", DashboardDataView.as_view(), name="nocturne-dashboard-data"),
]
