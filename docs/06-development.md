# 06 — Разработка и расширение

## Структура проекта

```
IoT-Smart Home/
  iot_gateway/
    __init__.py
    main.py              # FastAPI app, маршруты
    config.py            # Настройки из env (pydantic-settings)
    db.py                # Async engine, сессии, Base
    models.py            # SQLAlchemy: Device, Rule, EventLog
    schemas.py           # Pydantic: запросы/ответы API
    repositories/
      device.py          # CRUD и выборки по устройствам
      rule.py            # CRUD и выборка правил по event_type + device_id
      event_log.py       # Запись и чтение логов
    services/
      telekom_to_iot.py  # Входящий звонок → уведомление на endpoint
      iot_to_telekom.py # Webhook → правило → FreeSWITCH originate
    integrations/
      freeswitch.py      # Клиент originate (REST или ESL, иначе mock)
  scripts/
    init_db.sql          # Создание таблиц
  docs/                  # Документация
  requirements.txt
  .env.example
  README.md
```

## Добавление нового типа устройства

1. **Схема БД:** в `scripts/init_db.sql` в CHECK для `devices.type` добавить новое значение (при ручном управлении схемой). Либо использовать миграции (Alembic) и добавить значение в enum/check.
2. **Валидация API:** в `iot_gateway/schemas.py` в `DeviceCreate` обновить паттерн поля `type`, например: `pattern="^(speaker|sensor_smoke|doorphone)$"`.
3. **Логика:** при необходимости в `repositories/device.py` добавить функцию выбора по типу (аналогично `get_speaker_by_msisdn`). В сервисах использовать новый тип там, где нужно (например, сценарий домофона).

## Добавление нового типа события и правила

1. **Правила:** таблица `rules` уже хранит произвольный `event_type` и `action_type`. Новый сценарий (например, `doorbell` → `call`) можно реализовать без изменения схемы: создавать правила с `event_type=doorbell`, `action_type=call`, `target=номер`.
2. **Обработка webhook:** в `services/iot_to_telekom.py` функция `handle_webhook` ищет правило по `event_type` и `device_id` и выполняет действие по `action_type`. Для действия `call` уже вызывается FreeSWITCH. Другие действия (например, `send_sms`) потребуют расширения сервиса и, при необходимости, новой интеграции.

## Интеграция с FreeSWITCH

- **REST:** задать `FREESWITCH_REST_URL` в `.env`. В `integrations/freeswitch.py` используется путь `{base}/api/originate` и JSON-тело. Если ваш FreeSWITCH предоставляет другой URL или формат, измените `_originate_rest`.
- **ESL:** установить пакет `python-ESL`, не задавать `FREESWITCH_REST_URL`, указать `FREESWITCH_HOST`, `FREESWITCH_PORT`, `FREESWITCH_PASSWORD`. Команда отправляется через `bgapi originate ...`.
- **Mock:** при отсутствии REST URL и при неудачном импорте ESL вызов не выполняется, в лог пишется успех с пометкой mock — удобно для тестов без FreeSWITCH.

## Тестирование

- Запуск приложения: `uvicorn iot_gateway.main:app --reload --port 8000`.
- Проверка импорта: `python -c "from iot_gateway.main import app; print(app.openapi()['info'])`.
- Сценарии вручную: см. [05 — Сценарии использования](05-scenarios.md) и README.
- При необходимости добавить папку `tests/`, pytest и тесты для репозиториев/сервисов с тестовой БД (например, SQLite in-memory или отдельная PostgreSQL).

## Документы по архитектуре и планам

- В корне проекта: `iot-tas-module-architecture.md`, `iot-tas-module-prd-prototype.md`, `iot-tas-prototype-implementation-plan.md`, `iot-tas-prototype-done.md` — общая архитектура модуля, PRD прототипа, план реализации и перечень выполненных работ.
