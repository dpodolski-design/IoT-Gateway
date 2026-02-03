# План реализации минимального прототипа IoT-TAS модуля

**Обзор:** Реализация минимального прототипа модуля IoT-интеграции для TAS: REST API (Device Registry, Rules, webhook, симуляция входящего вызова, логи), интеграция с PostgreSQL и FreeSWITCH, два сценария — «входящий звонок → колонка» и «дым → звонок».

---

## Выбор стека

- **Язык и фреймворк:** Python 3.11+, FastAPI — быстрый REST API, встроенная валидация (Pydantic), асинхронность для вызовов к БД и HTTP.
- **БД:** PostgreSQL — драйвер `asyncpg` или SQLAlchemy 2.0 (async) для Device Registry, Rules и таблицы логов.
- **FreeSWITCH:** интеграция через **REST API** (mod_commands, `originate`) — проще для прототипа, чем ESL; один HTTP-запрос на создание вызова. Альтернатива: библиотека `python-ESL` при необходимости.
- **Конфигурация:** переменные окружения (`.env`) + `pydantic-settings`: `DATABASE_URL`, `FREESWITCH_URL`, `FREESWITCH_PASSWORD`, `WEBHOOK_API_KEY`, порт приложения.

## Структура проекта

```
IoT-Smart Home/
  iot_gateway/                 # основной пакет
    __init__.py
    main.py                    # FastAPI app, роуты
    config.py                  # настройки из env
    db.py                      # подключение к PostgreSQL, сессии
    models.py                  # SQLAlchemy модели или raw SQL-схема
    schemas.py                 # Pydantic для request/response
    repositories/              # слой доступа к данным (опционально, можно в crud.py)
      device.py
      rule.py
      event_log.py
    services/
      telekom_to_iot.py        # входящий звонок → уведомление на endpoint устройства
      iot_to_telekom.py        # webhook → поиск правила → FreeSWITCH originate
    integrations/
      freeswitch.py            # клиент REST/ESL к FreeSWITCH
  scripts/
    init_db.sql                # создание таблиц devices, rules, event_logs
  tests/                       # опционально для прототипа: 1–2 теста API
  .env.example
  requirements.txt
  README.md
```

## Схема данных (PostgreSQL)

**Таблица `devices`**

- `id` (UUID или serial PK), `device_id` (unique, строка — внешний идентификатор), `type` (enum или varchar: `speaker`, `sensor_smoke`), `msisdn` (номер), `subscriber_id` (nullable), `vendor`, `endpoint` (URL для уведомления колонки), `metadata` (JSONB), `created_at`, `updated_at`.

**Таблица `rules`**

- `id` (PK), `event_type` (varchar, напр. `smoke`), `device_id` (FK на devices или строка), `action_type` (varchar, напр. `call`), `target` (номер для звонка), `active` (boolean), `created_at`, `updated_at`.

**Таблица `event_logs`**

- `id` (PK), `event_kind` (varchar: `incoming_call_notify`, `smoke_trigger_call`), `device_id`, `rule_id` (nullable), `call_id` (nullable), `target_number` (nullable), `result` (success/failure), `details` (JSONB или text), `created_at`.

Файл `scripts/init_db.sql` — один скрипт создания таблиц без миграций (достаточно для прототипа).

## REST API (эндпоинты)

| Метод | Путь | Назначение |
|-------|------|------------|
| GET/POST | `/devices` | Список устройств / создание устройства |
| GET/PUT/DELETE | `/devices/{device_id}` | Получить/обновить/удалить устройство |
| GET | `/devices?msisdn=...` | Устройства по номеру (FR-DR-3) |
| GET/POST | `/rules` | Список правил / создание правила |
| GET/PUT/DELETE | `/rules/{id}` | Получить/обновить/удалить правило |
| POST | `/webhook` | Приём событий IoT (smoke и др.). Заголовок `X-API-Key`. Тело: `event_type`, `device_id`, опц. `timestamp`, `payload` (FR-IT-1, FR-IT-2). |
| POST | `/simulate/incoming-call` | Имитация входящего вызова (FR-K-2). Тело: `to_msisdn`, `from_cli`, опц. `call_id`. |
| GET | `/logs` | Список последних записей из `event_logs` (FR-L-2), query-параметр `limit` (по умолчанию 50). |

Админ/управление: те же эндпоинты устройств и правил; при необходимости защита заголовком `X-API-Key` (NFR-5).

## Потоки логики

**Телеком → IoT (входящий звонок):**

1. Вызов `POST /simulate/incoming-call` с `to_msisdn`, `from_cli`.
2. Поиск в `devices` по `msisdn = to_msisdn` и `type = speaker`.
3. Если найдено: HTTP POST на `endpoint` устройства с телом `{ "event": "incoming_call", "from_cli": "...", "call_id": "..." }`; запись в `event_logs` (event_kind = `incoming_call_notify`, result = success/failure).
4. Если не найдено — ответ 404 или 204, лог с result = failure.

**IoT → Телеком (датчик дыма):**

1. Вызов `POST /webhook` с заголовком `X-API-Key` и телом `{ "event_type": "smoke", "device_id": "..." }`.
2. Проверка API key (сравнение с конфигом).
3. Поиск устройства по `device_id`; поиск правила по `event_type` и привязке к устройству (или по event_type для данного device_id), `action_type = call`, `target` — номер.
4. Вызов интеграции FreeSWITCH: originate на `target` (и при возможности playback короткого аудио — опционально).
5. Запись в `event_logs`: event_kind = `smoke_trigger_call`, device_id, rule_id, target_number, result, call_id при наличии.

## Интеграция с FreeSWITCH

- **Метод:** REST API FreeSWITCH (например, `http://freeswitch:8080/api/originate` или порт по документации стенда). Команда `originate`: вызов на указанный номер с нужным gateway. Либо использование `lua`/`curl` внутри FreeSWITCH — снаружи модуль вызывает один HTTP endpoint, который на стороне FreeSWITCH выполняет originate (если прямой REST originate недоступен).
- В прототипе достаточно одного варианта: **прямой REST** к mod_commands (если доступен) или **ESL Inbound**: подключение к FreeSWITCH, отправка `bgapi originate ...`. Выбор за командой; в плане заложить абстракцию в `iot_gateway/integrations/freeswitch.py` (метод `originate(destination_number, ...)`) с реализацией через REST или ESL.
- Обработка ответа (успех/ошибка) и возврат результата в сервис для записи в `event_logs` (FR-FS-3).

## Безопасность (минимальная)

- Webhook: проверка заголовка `X-API-Key` против значения из конфига (FR-IT-2).
- Опционально: тот же ключ для `POST /simulate/incoming-call` и для управления устройствами/правилами, чтобы не оставлять API открытым на стенде.

## Документация и запуск

- **README.md:** описание назначения прототипа; требования (Python 3.11+, PostgreSQL, FreeSWITCH); установка (`pip install -r requirements.txt`); настройка `.env`; создание таблиц (`psql -f scripts/init_db.sql`); запуск (`uvicorn iot_gateway.main:app`); примеры curl для: создания устройства (speaker, sensor_smoke), создания правила (smoke → call), вызова `/simulate/incoming-call`, вызова `/webhook` с телом smoke; проверка `/logs` (NFR-4).
- **.env.example:** переменные `DATABASE_URL`, `FREESWITCH_HOST`, `FREESWITCH_PORT`, `FREESWITCH_PASSWORD`, `WEBHOOK_API_KEY`, `API_PORT`.

## Тестовый клиент «умная колонка»

Чтобы не зависеть от реальной колонки: встроить в проект эндпоинт `POST /test/notify` в самом FastAPI, который логирует тело в БД или в лог — и использовать в качестве endpoint устройства URL этого приложения (например `http://localhost:8000/test/notify`) для демо и проверки FR-TI-3.

## Порядок реализации (кратко)

1. Репозиторий: структура папок, `requirements.txt`, `config.py`, `.env.example`.
2. PostgreSQL: схема в `scripts/init_db.sql`, подключение и модели в `db.py` / `models.py`.
3. Pydantic-схемы и REST: устройства и правила (CRUD), логи (GET).
4. Сервис «телеком → IoT»: по `to_msisdn` найти speaker, POST на endpoint, лог в `event_logs`; эндпоинт `POST /simulate/incoming-call`.
5. Интеграция FreeSWITCH: клиент `originate`, вызов из сервиса.
6. Сервис «IoT → телеком»: `POST /webhook` — проверка API key, поиск правила, вызов FreeSWITCH, запись в `event_logs`.
7. Тестовый приёмник уведомлений: `POST /test/notify` для демо колонки.
8. README с примерами curl и опцией запуска без реального FreeSWITCH (мок или пропуск originate с записью в лог).

## Критерии приёмки (соответствие PRD разд. 7.1)

- Регистрация устройств speaker и sensor_smoke через API; привязка к msisdn и правилу — выполняется.
- Имитация входящего вызова через `POST /simulate/incoming-call` приводит к отправке уведомления на endpoint устройства (или на `/test/notify`) и записи в лог.
- Webhook с `event_type: smoke` и валидным `device_id` приводит к поиску правила и вызову FreeSWITCH originate на target; результат фиксируется в логах.
- Все срабатывания пишутся в `event_logs`.
- README и примеры позволяют воспроизвести сценарии на новом окружении.

После реализации прототип готов к демо на стенде с PostgreSQL и FreeSWITCH (или с моком FreeSWITCH для проверки потока без реального звонка).
