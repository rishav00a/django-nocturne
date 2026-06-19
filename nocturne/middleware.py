import sys
import time
import traceback

from django.conf import settings


def _get_setting(key, default=None):
    return getattr(settings, "NOCTURNE", {}).get(key, default)


class NocturneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exclude_paths = _get_setting("EXCLUDE_PATHS", ["/health", "/static", "/favicon.ico"])
        self.service_name = _get_setting("SERVICE_NAME", "default")

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        try:
            path = request.path
            if not any(path.startswith(p) for p in self.exclude_paths):
                self._record(request, response, elapsed_ms)
        except Exception:
            pass

        return response

    def process_exception(self, request, exception):
        try:
            exc_type, exc_value, exc_tb = sys.exc_info()
            stacktrace_str = "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)
            )
            request._nocturne_exception = {
                "exception_type": exc_type.__name__ if exc_type else "",
                "exception_message": str(exc_value)[:1000],
                "stacktrace": stacktrace_str,
            }
        except Exception:
            pass
        return None

    def _record(self, request, response, elapsed_ms):
        from .models import LogEntry

        exc_info = getattr(request, "_nocturne_exception", None)
        status = response.status_code

        if exc_info:
            level = "ERROR"
            message = exc_info["exception_message"] or f"HTTP {status} on {request.path}"
            stacktrace = exc_info["stacktrace"]
            exception_type = exc_info["exception_type"]
            exception_message = exc_info["exception_message"]
        else:
            stacktrace = None
            exception_type = None
            exception_message = None
            if status >= 500:
                level = "ERROR"
                message = f"HTTP {status} on {request.path}"
            elif status >= 400:
                level = "WARNING"
                message = f"{request.method} {request.path} → {status}"
            else:
                level = "INFO"
                message = f"{request.method} {request.path} → {status}"

        source_ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
        )

        LogEntry.objects.create(
            service_name=self.service_name,
            level=level,
            message=message,
            source_ip=source_ip or None,
            request_path=request.path,
            response_time_ms=round(elapsed_ms, 2),
            status_code=status,
            stacktrace=stacktrace,
            exception_type=exception_type,
            exception_message=exception_message,
        )
