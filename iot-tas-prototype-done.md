# Выполнено по плану прототипа IoT-TAS модуля

Краткое описание реализованного в соответствии с [планом реализации](iot-tas-prototype-implementation-plan.md).

---

## 1. Структура и конфигурация

- **requirements.txt** — FastAPI, uvicorn, pydantic-settings, asyncpg, SQLAlchemy 2 (async), httpx, python-dotenv
- **iot_gateway/config.py** — настройки из env (DATABASE_URL, FreeSWITCH, WEBHOOK_API_KEY, API_PORT)
- **.env.example** — пример переменных окружения
- Пакеты: `iot_gateway`, `repositories`, `services`, `integrations`

## 2. PostgreSQL

- **scripts/init_db.sql** — таблицы `devices`, `rules`, `event_logs` и индексы
- **iot_gateway/db.py** — async engine и сессии (async_sessionmaker)
- **iot_gateway/models.py** — модели Device, Rule, EventLog (SQLAlchemy 2)

## 3. REST API и данные

- **Devices:** GET/POST `/devices`, GET/PUT/DELETE `/devices/{device_id}`, фильтр `?msisdn=`
- **Rules:** GET/POST `/rules`, GET/PUT/DELETE `/rules/{id}`
- **Logs:** GET `/logs?limit=50`
- **iot_gateway/schemas.py** — Pydantic-схемы для запросов и ответов
- **iot_gateway/repositories/** — device, rule, event_log (CRUD и выборки)

## 4. Телеком → IoT (входящий звонок)

- **iot_gateway/services/telekom_to_iot.py** — по `to_msisdn` ищет колонку (speaker), отправляет POST на `endpoint` устройства, пишет в `event_logs`
- **POST /simulate/incoming-call** — тело: `to_msisdn`, `from_cli`, опционально `call_id`

## 5. Интеграция с FreeSWITCH

- **iot_gateway/integrations/freeswitch.py** — функция `originate(destination_number, ...)`: при заданном `FREESWITCH_REST_URL` используется REST, иначе попытка ESL; при отсутствии ESL — mock (успех без реального звонка)

## 6. IoT → Телеком (датчик дыма → звонок)

- **iot_gateway/services/iot_to_telekom.py** — по webhook ищет устройство и правило (event_type + device_id), выполняет действие (originate), пишет в `event_logs`
- **POST /webhook** — заголовок `X-API-Key`, тело: `event_type`, `device_id`; проверка ключа и вызов сервиса

## 7. Тестовый приёмник уведомлений

- **POST /test/notify** — принимает тело (имитация умной колонки), логирует и возвращает 200 — для демо и проверки сценария «звонок на колонку»

## 8. Документация

- **README.md** — установка, создание БД, запуск, примеры curl (устройства, правила, симуляция входящего, webhook, логи), раздел «Running without FreeSWITCH»

---

## Критерии приёмки (PRD 7.1)

- Регистрация устройств типа speaker и sensor_smoke через API; привязка к msisdn и правилу — выполняется
- Имитация входящего вызова через `POST /simulate/incoming-call` приводит к уведомлению на endpoint устройства (или `/test/notify`) и записи в лог
- Webhook с `event_type: smoke` и валидным `device_id` приводит к поиску правила и вызову FreeSWITCH originate (или mock); результат фиксируется в логах
- Все срабатывания пишутся в `event_logs`
- README и примеры позволяют воспроизвести сценарии на новом окружении
