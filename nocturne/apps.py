import warnings

from django.apps import AppConfig


class NocturneConfig(AppConfig):
    name = "nocturne"
    label = "nocturne"
    verbose_name = "Nocturne"
    default_auto_field = "django.db.models.BigAutoField"

    # Recognised keys in settings.NOCTURNE and their defaults:
    #   SERVICE_NAME          str   "default"             Tag applied by middleware
    #   ANOMALY_THRESHOLD     float 2.0                   Z-score cutoff
    #   RETENTION_DAYS        int   30                    Auto-purge log age (days)
    #   EXCLUDE_PATHS         list  ["/health", …]        Paths middleware skips
    #   LOGIN_URL             str   "/admin/login/"       Redirect for unauthenticated dashboard
    #   AI_BACKEND            str   "ollama"              Active LLM backend
    #   AI_DIAGNOSIS_ENABLED  bool  True                  Master toggle for all LLM calls
    #   ANTHROPIC_API_KEY     str   ""                    Claude API key
    #   ANTHROPIC_MODEL       str   "claude-sonnet-4-6"   Anthropic model ID
    #   OLLAMA_BASE_URL       str   "http://localhost:11434" Ollama server URL
    #   OLLAMA_MODEL          str   "llama3.2"            Ollama model name
    #   OPENAI_API_KEY        str   ""                    OpenAI (or compatible) API key
    #   OPENAI_MODEL          str   "gpt-4o"              OpenAI model ID
    #   OPENAI_BASE_URL       str   "https://api.openai.com/v1" Override for Azure/Groq/vLLM
    #   GEMINI_API_KEY        str   ""                    Google Gemini API key
    #   GEMINI_MODEL          str   "gemini-1.5-flash"    Gemini model ID
    #   WEBHOOK_SECRET        str   ""                    HMAC secret for received webhooks

    def ready(self):
        from django.conf import settings
        if not getattr(settings, "NOCTURNE", {}):
            warnings.warn(
                "NOCTURNE settings block not found in settings.py. "
                "Add NOCTURNE = {...} to your settings. "
                "Run: python manage.py nocturne_config for reference.",
                stacklevel=2,
            )
