Configuration
=============

All settings live in the ``NOCTURNE`` dict in your ``settings.py``.

.. code-block:: python

   NOCTURNE = {
       "SERVICE_NAME": "my-api",
       "ANOMALY_THRESHOLD": 2.0,
       "AI_BACKEND": "anthropic",
       "ANTHROPIC_API_KEY": env("ANTHROPIC_API_KEY"),
   }

Full Reference
--------------

Core
~~~~

.. list-table::
   :header-rows: 1

   * - Key
     - Default
     - Description
   * - ``SERVICE_NAME``
     - ``"default"``
     - Tag applied to all log entries by the middleware
   * - ``ANOMALY_THRESHOLD``
     - ``2.0``
     - Z-score cutoff for anomaly detection
   * - ``RETENTION_DAYS``
     - ``30``
     - Auto-purge log entries older than N days
   * - ``EXCLUDE_PATHS``
     - ``["/health", "/static", "/favicon.ico"]``
     - Paths the middleware skips
   * - ``LOGIN_URL``
     - ``"/admin/login/"``
     - Redirect for unauthenticated dashboard access

AI
~~

.. list-table::
   :header-rows: 1

   * - Key
     - Default
     - Description
   * - ``AI_BACKEND``
     - ``"ollama"``
     - Active LLM: ``anthropic`` / ``openai`` / ``ollama`` / ``gemini``
   * - ``AI_DIAGNOSIS_ENABLED``
     - ``True``
     - Master toggle for all LLM calls
   * - ``ANTHROPIC_API_KEY``
     - ``""``
     - Claude API key
   * - ``ANTHROPIC_MODEL``
     - ``"claude-sonnet-4-6"``
     - Claude model ID
   * - ``OLLAMA_BASE_URL``
     - ``"http://localhost:11434"``
     - Ollama server URL
   * - ``OLLAMA_MODEL``
     - ``"llama3.2"``
     - Ollama model name
   * - ``OPENAI_API_KEY``
     - ``""``
     - OpenAI API key
   * - ``OPENAI_MODEL``
     - ``"gpt-4o"``
     - OpenAI model ID
   * - ``OPENAI_BASE_URL``
     - ``"https://api.openai.com/v1"``
     - Override for Azure / Groq / vLLM
   * - ``GEMINI_API_KEY``
     - ``""``
     - Google Gemini API key
   * - ``GEMINI_MODEL``
     - ``"gemini-1.5-flash"``
     - Gemini model ID

Webhooks
~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Key
     - Default
     - Description
   * - ``WEBHOOK_SECRET``
     - ``""``
     - HMAC-SHA256 secret for signature validation on received webhooks
