# LLM Connector

Тонкий relay-сервис для OpenAI `Responses API`.

Сервис не хранит бизнес-логику классификации и не меняет prompt. Основной pipeline сам собирает полный OpenAI payload, а `llm-connector` только:
- проверяет Bearer-токен;
- применяет rate limit и базовые сетевые ограничения;
- отправляет запрос в OpenAI из разрешенной юрисдикции;
- возвращает обратно raw JSON-ответ OpenAI.

## Запуск

```bash
docker compose up --build gateway
```

Проверка:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Тесты:

```bash
docker compose --profile test run --rm tests
```

## Обязательные переменные окружения

- `OPENAI_API_KEY`
- `GATEWAY_AUTH_TOKEN`
- `DEFAULT_OPENAI_MODEL`
- `LOG_LEVEL`

Остальные параметры для timeout, retry, payload limit, rate limit, Sentry и IP allowlist описаны в `.env.example`.

## Пример запроса

```bash
curl -X POST http://localhost:8000/v1/openai/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-gateway-token" \
  -d '{
    "model": "gpt-5-mini",
    "text": {
      "format": {
        "type": "json_schema",
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
    "input": [
      {
        "role": "system",
        "content": [{"type": "input_text", "text": "Определи тип сайта по контексту и верни только JSON."}]
      },
      {
        "role": "user",
        "content": [{"type": "input_text", "text": "{\"domain\":\"verno.pro\",\"expected_city\":\"Краснодар\"}"}]
      }
    ]
  }'
```

## Развертывание

```bash
git clone https://github.com/kodjooo/llm-connector.git
cd llm-connector
cp .env.example .env
docker compose up -d --build gateway
```

Обновление:

```bash
git pull origin main
docker compose up -d --build gateway
```

Логи:

```bash
docker compose logs -f gateway
```

## Интеграция с основным pipeline

На основном сервере:
- `SITE_CLASSIFICATION_LLM_ENABLED=true`
- `SITE_CLASSIFICATION_LLM_PROVIDER=gateway`
- `SITE_CLASSIFICATION_LLM_GATEWAY_URL=https://<gateway-host>`
- `SITE_CLASSIFICATION_LLM_GATEWAY_API_KEY=<token>`

Основной pipeline сам формирует prompt, `input` и `text.format`, а relay лишь пересылает этот payload в OpenAI.
