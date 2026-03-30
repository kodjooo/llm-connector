# Архитектура LLM relay

## Назначение

`llm-connector` — это тонкий HTTP relay для OpenAI `chat/completions`. Он нужен, чтобы основной pipeline мог сохранить всю prompt-логику у себя, а на второй сервер вынести только сетевой доступ к OpenAI.

## Слои

- `app/main.py` — FastAPI-приложение, auth, middleware, health/readiness/metrics, endpoint relay.
- `app/schemas.py` — минимальная валидация входного OpenAI payload и error schema.
- `app/openai_client.py` — обертка над OpenAI SDK с timeout/retry.
- `app/service.py` — тонкий сервисный слой, который только вызывает upstream и пишет метрики.
- `app/rate_limit.py` и `app/metrics.py` — локальный rate limit и prometheus-метрики.

## Поток запроса

1. Клиент присылает `POST /v1/openai/chat-completions`.
2. Приложение проверяет Bearer token и IP allowlist.
3. Payload валидируется минимально: должны быть `messages`, прочие OpenAI-поля пропускаются как есть.
4. Relay вызывает OpenAI через официальный SDK.
5. Ответ `chat.completion` возвращается клиенту без доменной нормализации.

## Принцип “prompt only in main app”

- Relay не создает свой system prompt.
- Relay не понимает, что такое mall, agency или site classification.
- Relay не превращает результат в доменный JSON.
- Все это остается в основном pipeline, который может переиспользовать relay и для других задач.

## Конфигурация

Обязательные env:
- `OPENAI_API_KEY`
- `GATEWAY_AUTH_TOKEN`
- `DEFAULT_OPENAI_MODEL`
- `LOG_LEVEL`

Дополнительные env:
- timeout/retry
- payload limit
- rate limit
- Sentry
- allowed source IPs

## Безопасность

- `Authorization` не логируется.
- Полный prompt не логируется.
- Размер входного payload ограничен.
- Можно ограничить доступ по IP через `ALLOWED_SOURCE_IPS`.

## Наблюдаемость

- `GET /health`
- `GET /ready`
- `GET /metrics`
- JSON-логи с `request_id`, `status_code`, `model`, `duration_ms`

## Docker-модель

- `gateway` — основной контейнер сервиса
- `tests` — контейнер для прогона `pytest`

Сервис рассчитан на запуск через Docker Compose и обновление через `git pull origin main` + `docker compose up -d --build gateway`.
