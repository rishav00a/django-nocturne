# Changelog

All notable changes to django-nocturne will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-06-19

### Added
- `NocturneMiddleware` — zero-code request/response logging with exception capture and stacktrace recording
- Statistical anomaly detection via Z-score across 5-minute error-rate buckets (MEDIUM / HIGH / CRITICAL severity tiers)
- Multi-signal health scoring (0–100) combining error rate, response time, and volume signals
- AI-powered root-cause analysis via LangChain: supports Anthropic Claude, OpenAI GPT-4o, Google Gemini, and local Ollama models
- Webhook alerting — HMAC-SHA256 signed payloads with `WebhookEvent` delivery history
- Health trend tracking — per-service `HealthSnapshot` model; `snapshot_health` management command
- Real-time browser dashboard with Chart.js: error rate timeline, health bar chart with trend arrows, log level distribution, slowest endpoints, request volume sparkline, service status board
- Global timeframe filter (15M / 30M / 1H / 3H / 6H / 12H / 24H / 7D) controlling all charts simultaneously
- Log Explorer with expandable rows, syntax-highlighted stacktraces, and in-place AI analysis (4-state UX: idle → loading → result → cached)
- Anomaly detail modal with Z-score visualiser, AI diagnosis, and webhook delivery status
- Webhook Activity panel with live delivery feed and test webhook button
- Health Trends panel with per-service cards (colour-coded by trend direction)
- Full DRF REST API: health, logs, anomalies, webhooks, dashboard data
- Two-tier permission model: `nocturne.view_nocturne` (read) vs superuser (write/admin)
- `generate_demo_logs` management command: 975 entries, 3 realistic error spikes with stacktraces, seeded WebhookEvents and HealthSnapshots
- `nocturne_config` and `test_ai_diagnosis` management commands
- Django admin integration for all models
- Support for Django 4.0–5.0, Python 3.9–3.12

## [0.1.1] - 2026-06-19

### Added
- Live demo screenshots covering all dashboard features
- Screenshots gallery in ReadTheDocs

### Fixed
- CI Django/Python version matrix
- Added pytest-cov to dev dependencies
- Fixed .readthedocs.yaml configuration
- Replaced fury.io badges with shields.io
