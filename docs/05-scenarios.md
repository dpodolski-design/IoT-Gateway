# 05 — Сценарии использования

Во всех примерах предполагается, что API доступен по адресу `http://localhost:8000` и в `.env` задано `WEBHOOK_API_KEY=change-me-in-production` (или подставьте свой ключ в заголовок webhook).

## Сценарий 1: Входящий звонок → уведомление на умную колонку

Цель: при «входящем звонке» на номер абонента отправить уведомление на зарегистрированную колонку (или на тестовый эндпоинт).

### Шаг 1. Регистрация колонки

Привязываем колонку к номеру `79001234567`. В качестве `endpoint` указываем тестовый эндпоинт самого приложения — уведомления будут приходить на `/test/notify` и логироваться в консоль.

```bash
curl -X POST http://localhost:8000/devices ^
  -H "Content-Type: application/json" ^
  -d "{\"device_id\": \"speaker-1\", \"type\": \"speaker\", \"msisdn\": \"79001234567\", \"endpoint\": \"http://localhost:8000/test/notify\"}"
```

В ответ — объект устройства (id, device_id, type, msisdn, endpoint, ...).

### Шаг 2. Симуляция входящего вызова

Эмулируем входящий звонок на номер `79001234567` с номера `79001112233`.

```bash
curl -X POST http://localhost:8000/simulate/incoming-call ^
  -H "Content-Type: application/json" ^
  -d "{\"to_msisdn\": \"79001234567\", \"from_cli\": \"79001112233\"}"
```

Ожидаемый ответ: `{"notified": true, "device_id": "speaker-1", "error": null}`.  
В консоли приложения появится лог от `/test/notify` с телом `{"event": "incoming_call", "from_cli": "79001112233", "call_id": "..."}`.

### Шаг 3. Проверка логов

```bash
curl "http://localhost:8000/logs?limit=5"
```

В списке должна быть запись с `event_kind: "incoming_call_notify"`, `result: "success"`, `device_id: "speaker-1"`.

---

## Сценарий 2: Датчик дыма → звонок на номер

Цель: при событии «дым» от датчика инициировать звонок на заданный номер (через FreeSWITCH или mock).

### Шаг 1. Регистрация датчика дыма

```bash
curl -X POST http://localhost:8000/devices ^
  -H "Content-Type: application/json" ^
  -d "{\"device_id\": \"smoke-sensor-1\", \"type\": \"sensor_smoke\", \"msisdn\": \"79001234567\"}"
```

### Шаг 2. Создание правила

При событии `smoke` от устройства `smoke-sensor-1` выполнять действие `call` на номер `79007654321`.

```bash
curl -X POST http://localhost:8000/rules ^
  -H "Content-Type: application/json" ^
  -d "{\"event_type\": \"smoke\", \"device_id\": \"smoke-sensor-1\", \"action_type\": \"call\", \"target\": \"79007654321\"}"
```

### Шаг 3. Отправка webhook (срабатывание датчика)

Умный дом отправляет событие. Обязателен заголовок `X-API-Key`.

```bash
curl -X POST http://localhost:8000/webhook ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: change-me-in-production" ^
  -d "{\"event_type\": \"smoke\", \"device_id\": \"smoke-sensor-1\"}"
```

Ожидаемый ответ содержит `"success": true`, при наличии FreeSWITCH будет инициирован звонок на `79007654321`; без FreeSWITCH — mock (звонок только в логе).

### Шаг 4. Проверка логов

```bash
curl "http://localhost:8000/logs?limit=5"
```

Должна появиться запись с `event_kind: "smoke_trigger_call"`, `result: "success"`, `target_number: "79007654321"`.

---

## Дополнительные запросы

- Список устройств по номеру: `curl "http://localhost:8000/devices?msisdn=79001234567"`
- Список всех правил: `curl http://localhost:8000/rules`
- Удаление устройства: `curl -X DELETE http://localhost:8000/devices/speaker-1`
- Удаление правила: `curl -X DELETE http://localhost:8000/rules/1`

В средах с другим shell (Bash, PowerShell без `^`) используйте обратный слэш `\` для переноса строк или записывайте JSON в одну строку.
