# LLM Connector

Тонкий relay-сервис для OpenAI `chat/completions`.

Сервис не хранит бизнес-логику классификации и не меняет prompt. Основной pipeline сам собирает полный OpenAI payload, а `llm-connector` только:
- проверяет Bearer-токен;
- применяет rate limit и базовые сетевые ограничения;
- отправляет запрос в OpenAI из разрешенной юрисдикции;
- возвращает обратно raw JSON-ответ OpenAI.

## Запуск через Docker Desktop

```bash
docker compose up --build gateway
```

Проверка:

```bash
curl http://localhost:8000/health
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

- `OPENAI_API_KEY` — ключ OpenAI для сервера, где API доступен.
- `GATEWAY_AUTH_TOKEN` — общий Bearer-токен между pipeline и relay.
- `DEFAULT_OPENAI_MODEL` — fallback-модель, если клиент не прислал `model`.
- `LOG_LEVEL` — уровень логирования.

Остальные параметры для timeout, retry, payload limit, rate limit, Sentry и IP allowlist описаны в `.env.example`.

## Пример запроса

```bash
curl -X POST http://localhost:8000/v1/openai/chat-completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-gateway-token" \
  -d '{
    "model": "gpt-5-mini",
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "SiteClassification",
        "schema": {
          "type": "object",
          "properties": {
            "site_verdict": {"type": ["string", "null"]},
            "detected_city": {"type": ["string", "null"]},
            "confidence": {"type": "number"},
            "reason": {"type": ["string", "null"]}
          },
          "required": ["site_verdict", "detected_city", "confidence", "reason"]
        }
      }
    },
    "messages": [
      {"role": "system", "content": "Определи тип сайта по контексту и верни только JSON."},
      {"role": "user", "content": "{\"domain\":\"verno.pro\",\"expected_city\":\"Краснодар\"}"}
    ]
  }'
```

## Развертывание на удаленном сервере

1. Установить Docker Engine и Docker Compose Plugin.
2. Клонировать репозиторий:

```bash
git clone https://github.com/kodjooo/llm-connector.git
cd llm-connector
```

3. Создать `.env` на основе `.env.example` и заполнить секреты.
4. Запустить сервис:

```bash
docker compose up -d --build gateway
```

5. Проверить:

```bash
docker compose ps
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

6. Для обновления:

```bash
git pull origin main
docker compose up -d --build gateway
```

7. Для логов:

```bash
docker compose logs -f gateway
```

## Интеграция с основным pipeline

На основном сервере:

- `SITE_CLASSIFICATION_LLM_ENABLED=true`
- `SITE_CLASSIFICATION_LLM_PROVIDER=gateway`
- `SITE_CLASSIFICATION_LLM_GATEWAY_URL=https://<gateway-host>`
- `SITE_CLASSIFICATION_LLM_GATEWAY_API_KEY=<token>`

Основной pipeline сам формирует prompt, `messages` и `response_format`, а relay лишь пересылает этот payload в OpenAI.
