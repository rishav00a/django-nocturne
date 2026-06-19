AI Backends
===========

django-nocturne uses LangChain as a unified interface to multiple LLM providers.
Set ``AI_BACKEND`` in your ``NOCTURNE`` settings dict to switch providers.

Anthropic (Claude)
------------------

.. code-block:: bash

   pip install "django-nocturne[anthropic]"

.. code-block:: python

   NOCTURNE = {
       "AI_BACKEND": "anthropic",
       "ANTHROPIC_API_KEY": env("ANTHROPIC_API_KEY"),
       "ANTHROPIC_MODEL": "claude-sonnet-4-6",
   }

OpenAI (GPT / Azure / Groq)
----------------------------

.. code-block:: bash

   pip install "django-nocturne[openai]"

.. code-block:: python

   NOCTURNE = {
       "AI_BACKEND": "openai",
       "OPENAI_API_KEY": env("OPENAI_API_KEY"),
       "OPENAI_MODEL": "gpt-4o",
       # Override for Azure, Groq, LM Studio, vLLM:
       # "OPENAI_BASE_URL": "https://api.groq.com/openai/v1",
   }

Ollama (Local)
--------------

No API key required. Start Ollama and pull a model first:

.. code-block:: bash

   pip install "django-nocturne[ollama]"
   ollama pull llama3.2

.. code-block:: python

   NOCTURNE = {
       "AI_BACKEND": "ollama",
       "OLLAMA_BASE_URL": "http://localhost:11434",
       "OLLAMA_MODEL": "llama3.2",
   }

Google Gemini
-------------

.. code-block:: bash

   pip install "django-nocturne[gemini]"

.. code-block:: python

   NOCTURNE = {
       "AI_BACKEND": "gemini",
       "GEMINI_API_KEY": env("GEMINI_API_KEY"),
       "GEMINI_MODEL": "gemini-1.5-flash",
   }

Disabling AI
------------

Set ``AI_DIAGNOSIS_ENABLED = False`` to skip all LLM calls:

.. code-block:: python

   NOCTURNE = {
       "AI_DIAGNOSIS_ENABLED": False,
   }

Testing Your Backend
--------------------

.. code-block:: bash

   python manage.py test_ai_diagnosis
   python manage.py test_ai_diagnosis --backend anthropic
