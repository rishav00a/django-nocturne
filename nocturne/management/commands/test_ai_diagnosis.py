from unittest.mock import MagicMock

from django.core.management.base import BaseCommand

from nocturne.ai_diagnosis import _get_apm_setting, get_ai_diagnosis

_DIVIDER = "─" * 46
_BACKENDS = ["anthropic", "ollama", "openai", "gemini"]

_MODEL_KEYS = {
    "anthropic": ("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    "ollama":    ("OLLAMA_MODEL",    "llama3.2"),
    "openai":    ("OPENAI_MODEL",    "gpt-4o"),
    "gemini":    ("GEMINI_MODEL",    "gemini-1.5-flash"),
}


def _backend_status(name):
    if name == "anthropic":
        key   = _get_apm_setting("ANTHROPIC_API_KEY", "")
        model = _get_apm_setting("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        return f"✓ key set ({model})" if key else "✗ No API key configured"
    if name == "ollama":
        url   = _get_apm_setting("OLLAMA_BASE_URL", "http://localhost:11434")
        model = _get_apm_setting("OLLAMA_MODEL", "llama3.2")
        return f"✓ {url} ({model})"
    if name == "openai":
        key   = _get_apm_setting("OPENAI_API_KEY", "")
        model = _get_apm_setting("OPENAI_MODEL", "gpt-4o")
        return f"✓ key set ({model})" if key else "✗ No API key configured"
    if name == "gemini":
        key   = _get_apm_setting("GEMINI_API_KEY", "")
        model = _get_apm_setting("GEMINI_MODEL", "gemini-1.5-flash")
        return f"✓ key set ({model})" if key else "✗ No API key configured"
    return "unknown"


def _model_for(backend):
    key, default = _MODEL_KEYS.get(backend, ("OLLAMA_MODEL", "llama3.2"))
    return _get_apm_setting(key, default)


class Command(BaseCommand):
    help = "Show AI backend configuration and test the active (or a specific) backend."

    def add_arguments(self, parser):
        parser.add_argument(
            "--backend",
            choices=_BACKENDS,
            default=None,
            help="Test a specific backend instead of the currently active one.",
        )

    def handle(self, *args, **options):
        active  = _get_apm_setting("AI_BACKEND", "ollama").lower()
        enabled = _get_apm_setting("AI_DIAGNOSIS_ENABLED", True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[Nocturne] AI Backend Configuration"))
        self.stdout.write(_DIVIDER)
        self.stdout.write(f"AI_DIAGNOSIS_ENABLED : {'yes' if enabled else 'no'}")
        self.stdout.write(f"Active backend       : {active}")
        self.stdout.write(f"Interface            : LangChain")
        self.stdout.write("")
        self.stdout.write(f"{'Backend':<14} Status")
        self.stdout.write(_DIVIDER)
        for name in _BACKENDS:
            marker = "→" if name == active else " "
            self.stdout.write(f"{marker} {name:<12} {_backend_status(name)}")
        self.stdout.write(_DIVIDER)

        if not enabled:
            self.stdout.write(self.style.WARNING(
                "AI diagnosis is disabled (AI_DIAGNOSIS_ENABLED=False)."
            ))
            return

        target = options["backend"] or active
        if target not in _BACKENDS:
            self.stdout.write(self.style.WARNING(
                f"Backend '{target}' is not a supported LLM provider. "
                "Set AI_BACKEND to: anthropic, ollama, openai, or gemini"
            ))
            return

        self.stdout.write("")
        self.stdout.write(f"[Nocturne] AI Backend : {target}")
        self.stdout.write(f"[Nocturne] Model      : {_model_for(target)}")
        self.stdout.write(f"[Nocturne] Interface  : LangChain")
        self.stdout.write(f"[Nocturne] Testing...")

        mock_event = MagicMock()
        mock_event.service_name = "test-service"
        mock_event.severity     = "HIGH"
        mock_event.z_score      = 3.72
        mock_event.error_count  = 40
        mock_event.window_start = "2024-01-01 12:00:00"
        mock_event.window_end   = "2024-01-01 12:05:00"
        mock_event.pk           = 0
        mock_event.ai_diagnosis = ""

        if options["backend"] and options["backend"] != active:
            import django.conf
            original = django.conf.settings.NOCTURNE.get("AI_BACKEND")
            django.conf.settings.NOCTURNE["AI_BACKEND"] = options["backend"]
            try:
                get_ai_diagnosis(mock_event, [])
            finally:
                django.conf.settings.NOCTURNE["AI_BACKEND"] = original
        else:
            get_ai_diagnosis(mock_event, [])

        result   = mock_event.ai_diagnosis
        is_error = any(result.startswith(p) for p in [
            "AI diagnosis failed", "AI diagnosis disabled",
            "LangChain provider not installed",
        ])

        self.stdout.write(f"[Nocturne] Response   : {result}")
        self.stdout.write("")
        if is_error:
            self.stdout.write(self.style.ERROR(
                f"[Nocturne] ✗ Backend '{target}' is not working or not configured."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"[Nocturne] ✓ Working correctly."
            ))
