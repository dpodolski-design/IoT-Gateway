# 03 — Установка и настройка

## Требования

- **Python 3.11+**
- **PostgreSQL** (любая версия с поддержкой JSONB и async драйвера)
- **FreeSWITCH** — опционально; без него вызовы инициируются в режиме mock

Чтобы **POST /devices** и остальные эндпоинты с БД работали, нужно:

1. **Запустить PostgreSQL** (сервер доступен по адресу из `DATABASE_URL`).
2. **Создать БД** `iot_gateway` (или другое имя и указать его в `DATABASE_URL`).
3. **Выполнить** `scripts/init_db.sql` для создания таблиц.
4. **Указать верный** `DATABASE_URL` в `.env` (формат: `postgresql+asyncpg://user:password@host:5432/iot_gateway`).

При недоступности БД API возвращает **503** с сообщением: *"Database unavailable. Ensure PostgreSQL is running and DATABASE_URL in .env is correct."*

## Установка

### 1. Клонирование / переход в каталог проекта

```bash
cd "IoT-Smart Home"
```

### 2. Виртуальное окружение и зависимости

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### 3. База данных

Создать БД и применить схему:

```bash
createdb iot_gateway
psql -d iot_gateway -f scripts/init_db.sql
```

Или с явной строкой подключения:

```bash
psql "postgresql://user:password@localhost:5432/iot_gateway" -f scripts/init_db.sql
```

### 4. Конфигурация

Скопировать пример конфигурации и при необходимости отредактировать:

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # Linux/macOS
```

### 5. Запуск

```bash
uvicorn iot_gateway.main:app --reload --host 0.0.0.0 --port 8000
```

После запуска:

- API: http://localhost:8000
- Интерактивная документация: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

## Переменные окружения

Файл `.env` (или переменные окружения) читается через `pydantic-settings`. Пример и описание — в `.env.example`.

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| **DATABASE_URL** | Строка подключения к PostgreSQL (драйвер **asyncpg**). Пример: `postgresql+asyncpg://user:pass@host:5432/iot_gateway` | `postgresql+asyncpg://postgres:postgres@localhost:5432/iot_gateway` |
| **WEBHOOK_API_KEY** | Секрет для заголовка `X-API-Key` при вызове `/webhook` | `change-me-in-production` |
| **FREESWITCH_HOST** | Хост FreeSWITCH (для ESL) | `localhost` |
| **FREESWITCH_PORT** | Порт ESL | `8021` |
| **FREESWITCH_PASSWORD** | Пароль ESL | `ClueCon` |
| **FREESWITCH_REST_URL** | Базовый URL HTTP API FreeSWITCH (например `http://localhost:8080`). Если не задан — используется ESL или mock | — |
| **API_PORT** | Порт приложения (используется при запуске через конфиг, не uvicorn) | `8000` |

## Режим без FreeSWITCH

Если **не задавать** `FREESWITCH_REST_URL` и не использовать ESL:

- Обработка webhook и правил выполняется как обычно.
- При срабатывании правила «звонок» вызывается **mock** — в лог пишется успех, реальный звонок не инициируется.
- Это удобно для проверки сценариев без установленного FreeSWITCH.

## Проверка установки

```bash
python -c "from iot_gateway.main import app; print('OK')"
```

При успешном импорте выведется `OK`. Дальше можно выполнить примеры из [05 — Сценарии использования](05-scenarios.md) или вызвать эндпоинты через http://localhost:8000/docs.
