# 02 — Архитектура

## Компоненты

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI (main.py)                                       │
│  REST: /devices, /rules, /logs, /webhook,                │
│        /simulate/incoming-call, /test/notify            │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ repositories  │   │ services      │   │ integrations  │
│ device, rule, │   │ telekom_to_   │   │ freeswitch     │
│ event_log     │   │ iot, iot_to_  │   │ (originate)   │
│               │   │ telekom       │   │               │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL (devices, rules, event_logs)                  │
└─────────────────────────────────────────────────────────┘
```

- **repositories** — доступ к данным (устройства, правила, логи).
- **services** — бизнес-логика: «входящий звонок → уведомление на устройство» и «webhook → правило → звонок».
- **integrations** — вызов FreeSWITCH (REST или ESL; при недоступности — mock).

## Поток: Телеком → IoT (входящий звонок)

1. Вызов **POST /simulate/incoming-call** с `to_msisdn`, `from_cli`.
2. Поиск в `devices` записи с `msisdn = to_msisdn` и `type = speaker`.
3. Если найдено и задан `endpoint` — HTTP POST на `endpoint` с телом `{ "event": "incoming_call", "from_cli", "call_id" }`.
4. Запись в `event_logs`: `event_kind = incoming_call_notify`, `result = success|failure`.

## Поток: IoT → Телеком (датчик дыма)

1. Вызов **POST /webhook** с заголовком `X-API-Key` и телом `event_type`, `device_id`.
2. Проверка API key; поиск устройства и правила (event_type + device_id, action_type = call).
3. Вызов FreeSWITCH **originate** на номер из правила (`target`) или mock.
4. Запись в `event_logs`: `event_kind = smoke_trigger_call`, `result`, `target_number`, `details`.

## Схема данных (PostgreSQL)

**devices**

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | PK |
| device_id | VARCHAR(255) UNIQUE | Внешний идентификатор устройства |
| type | VARCHAR(64) | `speaker` или `sensor_smoke` |
| msisdn | VARCHAR(32) | Номер для привязки колонки |
| subscriber_id | VARCHAR(255) | Опционально |
| vendor | VARCHAR(128) | Опционально |
| endpoint | VARCHAR(512) | URL для уведомления (колонка) |
| metadata | JSONB | Произвольные данные |
| created_at, updated_at | TIMESTAMPTZ | |

**rules**

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | PK |
| event_type | VARCHAR(64) | Например `smoke` |
| device_id | VARCHAR(255) | Связь с устройством |
| action_type | VARCHAR(64) | Например `call` |
| target | VARCHAR(64) | Номер для звонка |
| active | BOOLEAN | |
| created_at, updated_at | TIMESTAMPTZ | |

**event_logs**

| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | PK |
| event_kind | VARCHAR(64) | `incoming_call_notify`, `smoke_trigger_call` |
| device_id | VARCHAR(255) | |
| rule_id | INTEGER | |
| call_id | VARCHAR(255) | |
| target_number | VARCHAR(64) | |
| result | VARCHAR(32) | success / failure |
| details | JSONB | Доп. информация |
| created_at | TIMESTAMPTZ | |

Скрипт создания таблиц: `scripts/init_db.sql`.
