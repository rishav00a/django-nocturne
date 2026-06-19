import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_apm_setting(key, default=None):
    return getattr(settings, "NOCTURNE", {}).get(key, default)


logger.info("ai_diagnosis.py loaded — backend: %s", _get_apm_setting("AI_BACKEND", "NOT SET"))


# ---------------------------------------------------------------------------
# LangChain model factory
# ---------------------------------------------------------------------------

def _get_llm():
    backend = _get_apm_setting("AI_BACKEND", "ollama")

    if backend == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=_get_apm_setting("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=_get_apm_setting("OLLAMA_MODEL", "llama3.2"),
            temperature=0.1,
        )

    if backend == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=_get_apm_setting("ANTHROPIC_API_KEY", ""),
            model=_get_apm_setting("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            temperature=0.1,
            max_tokens=256,
        )

    if backend == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=_get_apm_setting("OPENAI_API_KEY", ""),
            model=_get_apm_setting("OPENAI_MODEL", "gpt-4o"),
            base_url=_get_apm_setting("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            temperature=0.1,
            max_tokens=256,
        )

    if backend == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            google_api_key=_get_apm_setting("GEMINI_API_KEY", ""),
            model=_get_apm_setting("GEMINI_MODEL", "gemini-1.5-flash"),
            temperature=0.1,
            max_output_tokens=256,
        )

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_ai_diagnosis(anomaly_event, recent_logs):
    logger.info("get_ai_diagnosis() called — backend: %s", _get_apm_setting("AI_BACKEND", "ollama"))
    if not _get_apm_setting("AI_DIAGNOSIS_ENABLED", True):
        diagnosis = "AI diagnosis disabled."
        logger.debug("Watchdog AI: diagnosis disabled via settings.")
    else:
        try:
            llm = _get_llm()
            if llm is None:
                diagnosis = (
                    "AI diagnosis disabled. Set AI_BACKEND in NOCTURNE "
                    "settings to: anthropic, ollama, openai, or gemini"
                )
            else:
                from langchain_core.messages import HumanMessage, SystemMessage

                log_lines = [
                    f"[{log.timestamp:%Y-%m-%d %H:%M:%S}] [{log.level}] "
                    f"{log.request_path} status={log.status_code} "
                    f"rt={log.response_time_ms}ms  {log.message}"
                    for log in recent_logs[:50]
                ]
                log_dump = "\n".join(log_lines) or "(no recent logs)"

                messages = [
                    SystemMessage(content=(
                        "You are an expert SRE analyzing application logs. "
                        "Be concise. Respond in 3 sentences max."
                    )),
                    HumanMessage(content=(
                        f"Service: {anomaly_event.service_name}\n"
                        f"Anomaly: {anomaly_event.severity} spike, "
                        f"Z-score {anomaly_event.z_score:.2f}\n"
                        f"Error count: {anomaly_event.error_count}\n"
                        f"Window: {anomaly_event.window_start} → "
                        f"{anomaly_event.window_end}\n\n"
                        f"Recent logs:\n{log_dump}\n\n"
                        "What is the most likely root cause? "
                        "What immediate action should the on-call engineer take?"
                    )),
                ]

                response = llm.invoke(messages)
                diagnosis = response.content
                backend = _get_apm_setting("AI_BACKEND", "ollama")
                logger.info(
                    "Watchdog AI: backend=%r service=%r anomaly=%s → %d chars",
                    backend, anomaly_event.service_name, anomaly_event.pk, len(diagnosis),
                )

        except ImportError as exc:
            backend = _get_apm_setting("AI_BACKEND", "ollama")
            diagnosis = (
                f"LangChain provider not installed: {exc}. "
                f"Run: pip install django-nocturne-apm[{backend}]"
            )
            logger.warning("Watchdog AI: missing provider package — %s", exc)
        except Exception as exc:
            diagnosis = f"AI diagnosis failed ({type(exc).__name__}): {exc}"
            logger.error("Watchdog AI: backend error — %s: %s", type(exc).__name__, exc)

    anomaly_event.ai_diagnosis = diagnosis
    anomaly_event.ai_diagnosed_at = timezone.now()
    anomaly_event.save(update_fields=["ai_diagnosis", "ai_diagnosed_at"])


def get_log_analysis(log_entry, context_logs):
    """Return a 3-point root-cause analysis for a specific log entry."""
    if not _get_apm_setting("AI_DIAGNOSIS_ENABLED", True):
        return "AI diagnosis disabled."
    try:
        llm = _get_llm()
        if llm is None:
            return ("AI diagnosis disabled. Set AI_BACKEND in NOCTURNE "
                    "settings to: anthropic, ollama, openai, or gemini")

        from langchain_core.messages import HumanMessage, SystemMessage

        ctx_lines = [
            f"[{log.timestamp:%Y-%m-%d %H:%M:%S}] [{log.level}] "
            f"{log.request_path} status={log.status_code} rt={log.response_time_ms}ms  {log.message}"
            for log in context_logs
        ]
        ctx_dump = "\n".join(ctx_lines) or "(no surrounding logs)"

        # Build error section — use stacktrace if available, otherwise message
        exc_type = getattr(log_entry, "exception_type", None) or ""
        exc_msg  = getattr(log_entry, "exception_message", None) or log_entry.message
        stacktrace = getattr(log_entry, "stacktrace", None)

        if exc_type and stacktrace:
            error_section = (
                f"Exception: {exc_type}: {exc_msg}\n\n"
                f"Full Stacktrace:\n{stacktrace}"
            )
        elif exc_type:
            error_section = f"Exception: {exc_type}: {exc_msg}"
        else:
            error_section = f"Error message:\n{log_entry.message}"

        messages = [
            SystemMessage(content=(
                "You are an expert SRE analyzing application logs. "
                "Be concise. Answer in exactly 3 numbered points."
            )),
            HumanMessage(content=(
                f"Analyze this specific log error:\n"
                f"{error_section}\n\n"
                f"Surrounding context logs:\n{ctx_dump}\n\n"
                "Provide:\n"
                "1. Root cause (1 sentence)\n"
                "2. Immediate fix (1 sentence)\n"
                "3. Prevention measure (1 sentence)"
            )),
        ]
        response = llm.invoke(messages)
        backend = _get_apm_setting("AI_BACKEND", "ollama")
        logger.info("Watchdog AI log analysis: backend=%r log=%s → %d chars",
                    backend, log_entry.pk, len(response.content))
        return response.content
    except ImportError as exc:
        backend = _get_apm_setting("AI_BACKEND", "ollama")
        return (f"LangChain provider not installed: {exc}. "
                f"Run: pip install django-nocturne-apm[{backend}]")
    except Exception as exc:
        logger.error("Watchdog AI log analysis error — %s: %s", type(exc).__name__, exc)
        return f"AI analysis failed ({type(exc).__name__}): {exc}"
