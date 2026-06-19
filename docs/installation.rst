Installation
============

Requirements
------------

* Python 3.9+
* Django 4.0+
* djangorestframework >= 3.14
* numpy >= 1.24
* requests >= 2.28

Install
-------

.. code-block:: bash

   pip install django-nocturne

With an AI backend:

.. code-block:: bash

   pip install "django-nocturne[anthropic]"   # Claude
   pip install "django-nocturne[openai]"      # GPT-4o
   pip install "django-nocturne[ollama]"      # Local Llama
   pip install "django-nocturne[gemini]"      # Google Gemini

Quick Setup
-----------

1. Add to ``INSTALLED_APPS``:

   .. code-block:: python

      INSTALLED_APPS = [
          ...
          "nocturne",
      ]

2. Add middleware (at the end):

   .. code-block:: python

      MIDDLEWARE = [
          ...
          "nocturne.middleware.NocturneMiddleware",
      ]

3. Add URLs:

   .. code-block:: python

      urlpatterns = [
          path("nocturne/", include("nocturne.urls")),
          ...
      ]

4. Configure and migrate:

   .. code-block:: bash

      python manage.py migrate
      python manage.py runserver
