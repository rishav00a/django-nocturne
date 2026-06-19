import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-nocturne-example-secret-key-change-in-prod"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "nocturne",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "nocturne.middleware.NocturneMiddleware",
]

ROOT_URLCONF = "example_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

NOCTURNE = {
    # Core
    "WEBHOOK_URL": os.environ.get("NOCTURNE_WEBHOOK_URL", ""),
    "ANOMALY_THRESHOLD": 2.0,
    "RETENTION_DAYS": 30,
    "EXCLUDE_PATHS": ["/health", "/static", "/favicon.ico"],
    "SERVICE_NAME": "example-app",
    "LOGIN_URL": "/admin/login/",

    # AI backend selection: 'anthropic' | 'ollama' | 'openai' | 'gemini'
    "AI_BACKEND": "ollama",
    "AI_DIAGNOSIS_ENABLED": True,

    # Anthropic / Claude
    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
    "ANTHROPIC_MODEL": "claude-sonnet-4-6",

    # Ollama (local — no API key needed)
    "OLLAMA_BASE_URL": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    "OLLAMA_MODEL": os.environ.get("OLLAMA_MODEL", "llama3.2"),

    # OpenAI / ChatGPT (also works with Azure, Groq, LM Studio, vLLM)
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    "OPENAI_MODEL": "gpt-4o",
    "OPENAI_BASE_URL": "https://api.openai.com/v1",

    # Google Gemini
    "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
    "GEMINI_MODEL": "gemini-1.5-flash",

    # Webhook secret for HMAC-SHA256 signature validation
    "WEBHOOK_SECRET": os.environ.get("NOCTURNE_WEBHOOK_SECRET", ""),
}
