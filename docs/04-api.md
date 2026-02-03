# 04 — API

Базовый URL: `http://localhost:8000` (или хост/порт вашего развёртывания).

Интерактивная документация: **GET /docs**. Спецификация OpenAPI: **GET /openapi.json**.

## Аутентификация

- **POST /webhook** — обязателен заголовок **X-API-Key** со значением, совпадающим с `WEBHOOK_API_KEY` из конфигурации. При неверном или отсутствующем ключе возвращается **401 Unauthorized**.
- Остальные эндпоинты в прототипе аутентификации не требуют.

## Устройства (Devices)

### GET /devices

Список устройств.

**Query-параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| msisdn | string | Опционально. Фильтр по номеру (MSISDN). |

**Ответ:** массив объектов Device (см. ниже).

### POST /devices

Регистрация устройства.

**Тело запроса (JSON):**

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| device_id | string | да | Уникальный идентификатор устройства |
| type | string | да | `speaker` или `sensor_smoke` |
| msisdn | string | нет | Номер для привязки (для колонки) |
| subscriber_id | string | нет | |
| vendor | string | нет | |
| endpoint | string | нет | URL для уведомления (для колонки) |
| metadata | object | нет | Произвольный JSON |

**Ответ:** объект Device. При дубликате `device_id` — **409 Conflict**.

### GET /devices/{device_id}

Получение устройства по `device_id`.

**Ответ:** объект Device или **404 Not Found**.

### PUT /devices/{device_id}

Обновление устройства. В теле передаются только изменяемые поля (частичное обновление).

**Ответ:** объект Device или **404 Not Found**.

### DELETE /devices/{device_id}

Удаление устройства.

**Ответ:** **204 No Content** или **404 Not Found**.

### Модель Device (ответ)

| Поле | Тип |
|------|-----|
| id | integer |
| device_id | string |
| type | string |
| msisdn | string \| null |
| subscriber_id | string \| null |
| vendor | string \| null |
| endpoint | string \| null |
| metadata | object \| null |
| created_at | string (datetime ISO) |
| updated_at | string (datetime ISO) |

---

## Правила (Rules)

### GET /rules

Список всех правил.

**Ответ:** массив объектов Rule.

### POST /rules

Создание правила.

**Тело запроса (JSON):**

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| event_type | string | да | Тип события (напр. `smoke`) |
| device_id | string | да | Идентификатор устройства |
| action_type | string | нет | По умолчанию `call` |
| target | string | да | Номер для звонка |
| active | boolean | нет | По умолчанию true |

**Ответ:** объект Rule.

### GET /rules/{rule_id}

Получение правила по числовому `id`.

**Ответ:** объект Rule или **404 Not Found**.

### PUT /rules/{rule_id}

Обновление правила (частичное).

**Ответ:** объект Rule или **404 Not Found**.

### DELETE /rules/{rule_id}

Удаление правила.

**Ответ:** **204 No Content** или **404 Not Found**.

### Модель Rule (ответ)

| Поле | Тип |
|------|-----|
| id | integer |
| event_type | string |
| device_id | string |
| action_type | string |
| target | string |
| active | boolean |
| created_at | string (datetime ISO) |
| updated_at | string (datetime ISO) |

---

## Логи событий

### GET /logs

Список последних записей из `event_logs`.

**Query-параметры:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| limit | integer | 50 | Количество записей (1–500) |

**Ответ:** массив объектов EventLog.

### Модель EventLog (ответ)

| Поле | Тип |
|------|-----|
| id | integer |
| event_kind | string |
| device_id | string \| null |
| rule_id | integer \| null |
| call_id | string \| null |
| target_number | string \| null |
| result | string |
| details | object \| null |
| created_at | string (datetime ISO) |

Значения `event_kind`: `incoming_call_notify`, `smoke_trigger_call`.

---

## Сценарии

### POST /simulate/incoming-call

Имитация входящего вызова на номер. Используется для сценария «Телеком → IoT».

**Тело запроса (JSON):**

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| to_msisdn | string | да | Номер, на который «звонят» |
| from_cli | string | да | Номер звонящего (CLI) |
| call_id | string | нет | Идентификатор вызова |

**Ответ:** объект с полями `notified` (boolean), `device_id` (string | null), `error` (string | null).  
Если устройство-колонка для `to_msisdn` не найдено — **404 Not Found**.

### POST /webhook

Приём событий от умного дома (IoT → Телеком). Обязателен заголовок **X-API-Key**.

**Тело запроса (JSON):**

| Поле | Тип | Обязательное | Описание |
|------|-----|--------------|----------|
| event_type | string | да | Тип события (напр. `smoke`) |
| device_id | string | да | Идентификатор устройства |
| timestamp | string | нет | |
| payload | object | нет | Доп. данные |

**Ответ:** объект с полями `success` (boolean), `rule_id`, `target`, `call_result`.  
При неверном API key — **401 Unauthorized**.

### POST /test/notify

Демо-эндпоинт для приёма уведомлений (имитация умной колонки). Принимает произвольный JSON, логирует тело и возвращает **200 OK** с полем `received` (присланное тело). Используется как `endpoint` устройства при тестах (например, `http://localhost:8000/test/notify`).
