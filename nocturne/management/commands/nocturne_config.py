from django.conf import settings
from django.core.management.base import BaseCommand

_DIVIDER = "─" * 46

_KEYS = [
    # AI routing
    ("AI_BACKEND",           "ollama",                    False),
    ("AI_DIAGNOSIS_ENABLED", True,                        False),
    # Ollama
    ("OLLAMA_BASE_URL",      "http://localhost:11434",    False),
    ("OLLAMA_MODEL",         "llama3.2",                  False),
    # Anthropic
    ("ANTHROPIC_API_KEY",    "",                          True),
    ("ANTHROPIC_MODEL",      "claude-sonnet-4-6",         False),
    # OpenAI
    ("OPENAI_API_KEY",       "",                          True),
    ("OPENAI_MODEL",         "gpt-4o",                    False),
    ("OPENAI_BASE_URL",      "https://api.openai.com/v1", False),
    # Gemini
    ("GEMINI_API_KEY",       "",                          True),
    ("GEMINI_MODEL",         "gemini-1.5-flash",          False),
    # Core
    ("WEBHOOK_URL",          "",                          False),
    ("WEBHOOK_SECRET",       "",                          True),
    ("ANOMALY_THRESHOLD",    2.0,                         False),
    ("RETENTION_DAYS",       30,                          False),
    ("SERVICE_NAME",         "default",                   False),
    ("LOGIN_URL",            "/admin/login/",             False),
    ("EXCLUDE_PATHS",        [],                          False),
]


class Command(BaseCommand):
    help = "Print the fully resolved NOCTURNE configuration and database stats."

    def handle(self, *args, **options):
        from django.db import connection
        cfg = getattr(settings, "NOCTURNE", {})

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[Nocturne] Resolved Configuration"))
        self.stdout.write(_DIVIDER)

        for key, default, is_secret in _KEYS:
            raw = cfg.get(key, default)
            display = "(set)" if (is_secret and raw) else ("(not set)" if is_secret else str(raw))
            self.stdout.write(f"{key:<22}: {display}")

        known = {k for k, _, _ in _KEYS}
        extras = set(cfg.keys()) - known
        if extras:
            self.stdout.write(self.style.WARNING(
                f"\nUnrecognised keys in NOCTURNE: {sorted(extras)}"
            ))

        # Database stats section
        self.stdout.write(_DIVIDER)
        db_engine = settings.DATABASES.get("default", {}).get("ENGINE", "unknown").split(".")[-1]
        self.stdout.write(f"{'Database':<22}: {db_engine}")

        try:
            from nocturne.models import AnomalyEvent, LogEntry, WebhookConfig
            log_count     = LogEntry.objects.count()
            anomaly_count = AnomalyEvent.objects.count()
            wh_total      = WebhookConfig.objects.count()
            wh_active     = WebhookConfig.objects.filter(is_active=True).count()
            self.stdout.write(f"{'Total LogEntries':<22}: {log_count}")
            self.stdout.write(f"{'Total AnomalyEvents':<22}: {anomaly_count}")
            self.stdout.write(f"{'Total WebhookConfigs':<22}: {wh_total} ({wh_active} active)")
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Could not query DB: {exc}"))

        self.stdout.write(_DIVIDER)
        self.stdout.write("")
