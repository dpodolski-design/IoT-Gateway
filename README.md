# IoT Gateway — Prototype TAS IoT Integration Module

Minimal prototype for the IoT integration module of a Telephony Application Server (TAS) platform. Implements two flows: **incoming call → smart speaker notification** and **smoke sensor event → outbound call** via FreeSWITCH.

## Requirements

- Python 3.11+
- PostgreSQL
- FreeSWITCH (optional for demo: see [Running without FreeSWITCH](#running-without-freeswitch))

Чтобы **POST /devices** (и остальные эндпоинты с БД) работал, необходимо:

1. **Запустить PostgreSQL** (сервер должен быть доступен по адресу из `DATABASE_URL`).
2. **Создать БД** `iot_gateway` (или другое имя и указать его в `DATABASE_URL`).
3. **Выполнить** `scripts/init_db.sql` для создания таблиц.
4. **Указать верный** `DATABASE_URL` в `.env` (формат: `postgresql+asyncpg://user:password@host:5432/iot_gateway`).

Если БД недоступна, API вернёт **503** с сообщением *"Database unavailable. Ensure PostgreSQL is running and DATABASE_URL in .env is correct."*

## Setup

1. **Create virtualenv and install dependencies**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Configure environment**

   Copy `.env.example` to `.env` and set at least:

   - `DATABASE_URL` — PostgreSQL connection string (async driver: `postgresql+asyncpg://user:pass@host:5432/dbname`)
   - `WEBHOOK_API_KEY` — secret for webhook authentication

   **Do not commit `.env`** — it is in `.gitignore`; keep real credentials only locally.

   Leave `FREESWITCH_REST_URL` unset to run without a real FreeSWITCH (originate will be mocked and logged).

3. **Create database and tables**

   ```bash
   createdb iot_gateway
   psql -d iot_gateway -f scripts/init_db.sql
   ```

   Or with a custom connection:

   ```bash
   psql "postgresql://user:pass@localhost:5432/iot_gateway" -f scripts/init_db.sql
   ```

4. **Run the API**

   ```bash
   uvicorn iot_gateway.main:app --reload --host 0.0.0.0 --port 8000
   ```

   API docs: http://localhost:8000/docs

## API Examples (curl)

Base URL: `http://localhost:8000`. Set `WEBHOOK_API_KEY=change-me-in-production` in `.env` for these examples (or use your value in the webhook call).

### 1. Register a smart speaker (for incoming-call notifications)

```bash
curl -X POST http://localhost:8000/devices \
  -H "Content-Type: application/json" \
  -d "{\"device_id\": \"speaker-1\", \"type\": \"speaker\", \"msisdn\": \"79001234567\", \"endpoint\": \"http://localhost:8000/test/notify\"}"
```

Using `/test/notify` as `endpoint` makes the gateway POST incoming-call events to its own demo endpoint (logged in console). For a real device, set `endpoint` to the device notification URL.

### 2. Register a smoke sensor device

```bash
curl -X POST http://localhost:8000/devices \
  -H "Content-Type: application/json" \
  -d "{\"device_id\": \"smoke-sensor-1\", \"type\": \"sensor_smoke\", \"msisdn\": \"79001234567\"}"
```

### 3. Create a rule: on smoke event → call number

```bash
curl -X POST http://localhost:8000/rules \
  -H "Content-Type: application/json" \
  -d "{\"event_type\": \"smoke\", \"device_id\": \"smoke-sensor-1\", \"action_type\": \"call\", \"target\": \"79007654321\"}"
```

### 4. Simulate incoming call (Telekom → IoT)

Incoming call to `79001234567` will trigger a POST to the speaker’s `endpoint` (here: `/test/notify`).

```bash
curl -X POST http://localhost:8000/simulate/incoming-call \
  -H "Content-Type: application/json" \
  -d "{\"to_msisdn\": \"79001234567\", \"from_cli\": \"79001112233\"}"
```

Check logs: `GET /logs` and the app console (for `/test/notify`).

### 5. Send smoke webhook (IoT → Telekom)

Requires `X-API-Key` header. Triggers the rule and calls FreeSWITCH originate (or mock if no FreeSWITCH).

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-in-production" \
  -d "{\"event_type\": \"smoke\", \"device_id\": \"smoke-sensor-1\"}"
```

### 6. List event logs

```bash
curl "http://localhost:8000/logs?limit=20"
```

## Running without FreeSWITCH

- Do **not** set `FREESWITCH_REST_URL` in `.env`.
- The gateway will still process webhooks and rules; when it needs to place a call it will use a **mock** originate (no real call, result is logged as success in `event_logs`).
- You can verify the full flow: register device → create rule → POST `/webhook` → check `/logs` for `smoke_trigger_call` with `result: success` and optional `mock: true` in details.

## Optional: FreeSWITCH

- Set `FREESWITCH_REST_URL` to your FreeSWITCH HTTP API base (e.g. `http://localhost:8080`) if your setup exposes an originate endpoint.
- Or use ESL: set `FREESWITCH_HOST`, `FREESWITCH_PORT`, `FREESWITCH_PASSWORD` and install `python-ESL`; leave `FREESWITCH_REST_URL` unset so the client uses ESL.

## Документация

Полная документация по проекту — в папке **[docs/](docs/README.md)**:

- [01 — Обзор и назначение](docs/01-overview.md)
- [02 — Архитектура](docs/02-architecture.md)
- [03 — Установка и настройка](docs/03-installation.md)
- [04 — API](docs/04-api.md)
- [05 — Сценарии использования](docs/05-scenarios.md)
- [06 — Разработка и расширение](docs/06-development.md)

## Project layout

- `iot_gateway/` — FastAPI app, config, DB models, repositories, services (telekom→IoT, IoT→telekom), FreeSWITCH integration
- `scripts/init_db.sql` — PostgreSQL schema (devices, rules, event_logs)
- `docs/` — документация проекта
- See `iot-tas-module-prd-prototype.md` and `iot-tas-prototype-implementation-plan.md` for requirements and implementation plan.
