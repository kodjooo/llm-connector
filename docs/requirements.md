ТЗ: тонкий LLM relay для OpenAI

1. Цель
Сервис нужен для того, чтобы основной pipeline не ходил в OpenAI напрямую с прод-сервера. Бизнес-логика, prompt и разбор результата остаются в основном проекте. Gateway выступает только как transport-слой.

2. Что должен делать сервис
- Принимать HTTP POST-запросы от доверенного pipeline.
- Проверять `Authorization: Bearer <token>`.
- Принимать почти готовый payload для OpenAI `chat/completions`.
- Вызывать OpenAI с заданной моделью и дополнительными полями payload без изменения prompt.
- Возвращать raw JSON-ответ OpenAI в совместимом формате.
- Логировать request_id, код ответа, длительность и модель без утечки чувствительных данных.
- Поддерживать health/readiness и endpoint метрик.

3. Обязательный endpoint
`POST /v1/openai/chat-completions`

4. Healthcheck
`GET /health` и `GET /ready` должны возвращать `{"status":"ok"}`.

5. Авторизация
- Основной способ: `Authorization: Bearer <token>`.
- Токен хранится на стороне relay как `GATEWAY_AUTH_TOKEN`.
- Тот же токен хранится на стороне pipeline как `SITE_CLASSIFICATION_LLM_GATEWAY_API_KEY`.
- Без валидного токена сервис возвращает `401`.

6. Входной JSON
Сервис принимает OpenAI-совместимый payload для `chat/completions`.
Минимум:

```json
{
  "model": "gpt-5-mini",
  "messages": [
    {"role": "system", "content": "Определи тип сайта по контексту и верни только JSON."},
    {"role": "user", "content": "{\"domain\":\"verno.pro\",\"expected_city\":\"Краснодар\"}"}
  ]
}
```

Дополнительные поля вроде `response_format`, `temperature`, `top_p` и т.п. должны передаваться прозрачно.

7. Выходной JSON
Сервис возвращает raw JSON OpenAI `chat.completion` без дополнительной нормализации бизнес-полей.

8. Ошибки
- `400` — невалидный JSON или некорректный payload.
- `401` — отсутствующий или неверный токен.
- `429` — локальный rate limit.
- `502` — OpenAI вернул upstream-ошибку или некорректный ответ.
- `504` — timeout при вызове OpenAI.

Формат ошибки:

```json
{
  "error": {
    "code": "upstream_timeout",
    "message": "OpenAI request timed out"
  }
}
```

9. Требования к логике relay
- Relay не должен менять `messages`, `response_format` или другие OpenAI-поля.
- Relay не должен добавлять собственный system prompt.
- Relay может подставить `DEFAULT_OPENAI_MODEL`, только если клиент не прислал `model`.
- Должны быть retry и timeout для upstream OpenAI.

10. Безопасность
- Не логировать `Authorization`.
- Не логировать полный пользовательский prompt целиком.
- Ограничить размер входного payload.
- Поддержать allowlist IP через env.

11. Развертывание
- FastAPI + Docker Compose.
- Отдельный сервер или VPS в разрешенной юрисдикции.
- Обязательные env:
  - `OPENAI_API_KEY`
  - `GATEWAY_AUTH_TOKEN`
  - `DEFAULT_OPENAI_MODEL`
  - `LOG_LEVEL`

12. Наблюдаемость
- Метрики:
  - `requests_total`
  - `requests_failed_total`
  - `upstream_openai_latency_ms`
  - `upstream_openai_errors_total`
- Логи:
  - `request_id`
  - `status_code`
  - `model`
  - `duration_ms`

13. Совместимость с текущим pipeline
- Основной pipeline должен уметь переключаться на `SITE_CLASSIFICATION_LLM_PROVIDER=gateway`.
- При этом prompt и схема ответа должны жить только в основном проекте.
- Gateway должен быть переиспользуемым и для других LLM-задач, не только для site classification.
