REST API
========

All endpoints are mounted under the prefix you chose in ``urls.py``
(``/nocturne/`` in the examples below).

Authentication
--------------

Two permission tiers:

* **view** — superuser *or* user with ``nocturne.view_nocturne`` permission
* **admin** — superuser only

Endpoints
---------

Health
~~~~~~

``GET /nocturne/api/health/?timeframe=1h``

Returns system health summary for the given timeframe window.

Logs
~~~~

``GET /nocturne/api/logs/``
  Paginated log entries. Accepts ``?timeframe=``, ``?service=``, ``?level=``, ``?search=``.
  Response uses the *light* serializer (no stacktrace).

``GET /nocturne/api/logs/<id>/``
  Full log entry including stacktrace.

``POST /nocturne/api/logs/ingest/``
  External log ingestion.

``POST /nocturne/api/logs/<id>/analyse/``
  Trigger AI root-cause analysis for a specific log entry.

Anomalies
~~~~~~~~~

``GET /nocturne/api/anomalies/``
  List anomaly events. Accepts ``?timeframe=``, ``?severity=``, ``?resolved=``.

``PATCH /nocturne/api/anomalies/<id>/``
  Mark an anomaly as resolved. *(admin)*

``POST /nocturne/api/detect/``
  Run anomaly detection scan immediately. *(admin)*

Dashboard
~~~~~~~~~

``GET /nocturne/api/dashboard/data/?timeframe=1h``
  All chart data in one response: error series, health scores, level distribution,
  recent anomalies, slowest endpoints, request volume, health trends.

Webhooks
~~~~~~~~

``GET  /nocturne/api/webhooks/``        List webhook configurations. *(admin)*
``POST /nocturne/api/webhooks/``        Create webhook configuration. *(admin)*
``PUT  /nocturne/api/webhooks/<id>/``   Update webhook configuration. *(admin)*
``DELETE /nocturne/api/webhooks/<id>/`` Delete webhook configuration. *(admin)*
``GET  /nocturne/api/webhooks/events/`` Delivery history. *(view)*
``POST /nocturne/api/webhooks/test/``   Send test ping to all active configs. *(admin)*
``POST /nocturne/api/webhook/receive/`` Simulated receiver endpoint. *(admin)*
