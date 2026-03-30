# LLM gateway для site classification

Сервис принимает запросы от основного pipeline, проверяет Bearer-токен, вызывает OpenAI из разрешенной юрисдикции и возвращает только нормализованный JSON-результат классификации сайта.

## Запуск через Docker Desktop

```bash
docker compose up --build gateway
```

Проверка healthcheck:

```bash
curl http://localhost:8000/health
```

Проверка readiness:

```bash
curl http://localhost:8000/ready
```

Запуск тестов:

```bash
docker compose --profile test run --rm tests
```

Остановка:

```bash
docker compose down
```

## Обязательные переменные окружения

- `OPENAI_API_KEY` — ключ OpenAI для окружения, где API доступен.
- `GATEWAY_AUTH_TOKEN` — Bearer-токен между pipeline и gateway.
- `DEFAULT_OPENAI_MODEL` — модель по умолчанию.
- `LOG_LEVEL` — уровень логирования.

Дополнительные параметры для timeout, retry, payload limit, rate limit, Sentry и сетевых ограничений описаны в `.env.example`.

## Пример запроса

```bash
curl -X POST http://localhost:8000/v1/site-classification \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-gateway-token" \
  -d '{
    "schema": "site_classification_v1",
    "model": "gpt-5-mini",
    "input": {
      "expected_city": "Краснодар",
      "expected_entity_type": "real_estate_agency",
      "domain": "verno.pro",
      "serp": {
        "title": "VERNO",
        "snippet": "Недвижимость в Краснодаре",
        "url": "https://verno.pro/",
        "position": 3
      },
      "serp_screening": {
        "score": 2.5,
        "reason": "serp_needs_homepage_verification",
        "requires_verification": true
      },
      "homepage_screening": {
        "score": 5.0,
        "reason": null,
        "requires_verification": null
      },
      "homepage_excerpt": "Каталог объектов..."
    }
  }'
```

## Развертывание на удаленном сервере

1. Установить Docker Engine с поддержкой Compose.
2. Скопировать проект и заполнить `.env` реальными секретами.
3. Запустить `docker compose up -d --build`.
4. Разместить сервис за reverse proxy или внутри private network/VPN.
5. Разрешить вход только от основного сервера или через защищенную сеть.

## Интеграция с pipeline

Для включения gateway в основном pipeline достаточно задать:

- `SITE_CLASSIFICATION_LLM_ENABLED=true`
- `SITE_CLASSIFICATION_LLM_PROVIDER=gateway`
- `SITE_CLASSIFICATION_LLM_GATEWAY_URL=https://<gateway-host>`
- `SITE_CLASSIFICATION_LLM_GATEWAY_API_KEY=<token>`
