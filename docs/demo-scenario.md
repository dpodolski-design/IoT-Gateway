# Инструкция по сценарию демонстрации прототипа IoT Gateway

Пошаговый сценарий для проведения демо двух потоков: «входящий звонок → колонка» и «датчик дыма → звонок».

---

## Подготовка к демо

### 1. Окружение

- Установлены зависимости: `pip install -r requirements.txt`
- PostgreSQL: создана БД, выполнен скрипт `scripts/init_db.sql`
- В корне проекта создан файл `.env` с переменными:
  - `DATABASE_URL` — строка подключения к БД (например `postgresql+asyncpg://postgres:postgres@localhost:5432/iot_gateway`)
  - `WEBHOOK_API_KEY` — для демо можно оставить `change-me-in-production`

### 2. Запуск

В терминале из каталога проекта:

```bash
uvicorn iot_gateway.main:app --reload --port 8000
```

В браузере открыть **http://localhost:8000/docs** (Swagger UI) — с него удобно выполнять запросы во время демо.

### 3. Режим без FreeSWITCH

Для демо не обязательно поднимать FreeSWITCH: не задавайте в `.env` переменную `FREESWITCH_REST_URL`. Тогда при срабатывании правила «звонок» будет использоваться mock — сценарий отработает, результат запишется в логи, реальный звонок не пойдёт.

---

## Часть 1: Телеком → IoT (звонок на колонку)

### Шаг 1. Показать реестр устройств

- В Swagger: **GET /devices** → Execute.
- Ответ: пустой список `[]`.

### Шаг 2. Зарегистрировать умную колонку

- **POST /devices**
- Тело запроса (JSON):

```json
{
  "device_id": "speaker-1",
  "type": "speaker",
  "msisdn": "79001234567",
  "endpoint": "http://localhost:8000/test/notify"
}
```

Пояснение: номер `79001234567` привязан к колонке; уведомления о входящих звонках будут отправляться на `endpoint`. Для демо указан наш же сервер (`/test/notify`) — уведомление придёт в приложение и залогируется.

### Шаг 3. Симуляция входящего вызова

- **POST /simulate/incoming-call**
- Тело запроса:

```json
{
  "to_msisdn": "79001234567",
  "from_cli": "79001112233"
}
```

Показать ответ: `notified: true`, `device_id: "speaker-1"`. В консоли uvicorn появится лог от **POST /test/notify** с телом `event: incoming_call`, `from_cli`, `call_id` — «колонка получила уведомление».

### Шаг 4. Проверка в логах

- **GET /logs** (или **GET /logs?limit=10**)
- Найти запись с `event_kind: "incoming_call_notify"`, `result: "success"`.

---

## Часть 2: IoT → Телеком (датчик дыма → звонок)

### Шаг 1. Зарегистрировать датчик дыма

- **POST /devices**
- Тело запроса:

```json
{
  "device_id": "smoke-sensor-1",
  "type": "sensor_smoke",
  "msisdn": "79001234567"
}
```

### Шаг 2. Создать правило

- **POST /rules**
- Тело запроса:

```json
{
  "event_type": "smoke",
  "device_id": "smoke-sensor-1",
  "action_type": "call",
  "target": "79007654321"
}
```

Пояснение: при событии `smoke` от устройства `smoke-sensor-1` модуль инициирует звонок на номер `79007654321` (через FreeSWITCH или mock).

### Шаг 3. Имитация срабатывания датчика (webhook)

- **POST /webhook**
- В Swagger добавить заголовок: **X-API-Key** = `change-me-in-production` (или значение `WEBHOOK_API_KEY` из `.env`)
- Тело запроса:

```json
{
  "event_type": "smoke",
  "device_id": "smoke-sensor-1"
}
```

Показать ответ: `success: true`. При работе без FreeSWITCH в `call_result` может быть `mock: true`.

### Шаг 4. Проверка в логах

- **GET /logs**
- Найти запись с `event_kind: "smoke_trigger_call"`, `result: "success"`, `target_number: "79007654321"`.

---

## Что подчеркнуть аудитории

- **Единый слой интеграции:** IoT Gateway стоит между TAS и умным домом; реестр устройств и правил в PostgreSQL.
- **Два направления:** телеком → IoT (уведомление на колонку) и IoT → телеком (событие → звонок).
- **Без переделки ядра TAS:** входящий вызов пока имитируется через REST; при интеграции с Kamailio/FreeSWITCH можно подставлять реальные события.
- **Расширяемость:** те же API и модель данных подходят для развития (SMS, домофон, браслет) по архитектурному документу.

---

## Советы

- Держать открытыми вкладку Swagger (http://localhost:8000/docs) и консоль uvicorn.
- Один раз пройти оба сценария заранее, чтобы не искать эндпоинты во время демо.
- Подробные примеры curl — в [05 — Сценарии использования](05-scenarios.md) и в [README.md](../README.md).
