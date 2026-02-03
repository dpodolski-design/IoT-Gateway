# Технический документ: IoT Integration Module (IIM) для TAS-платформы (Kamailio + FreeSWITCH + PostgreSQL)

**Дата:** 2026-02-03  
**Версия:** 1.0  
**Статус:** Draft (для согласования)  
**Автор:** вендор

---

## 1. Цели и бизнес-требования

### 1.1. Цель
Разработать модуль **IoT Integration Module (IIM)** для сервисной платформы оператора связи, обеспечивающий двустороннюю интеграцию между телеком-сервисами (голос/SIP, SMS) и экосистемами умного дома с фокусом на:

- **Телеком → умный дом**
  - прием **входящих звонков** на умные колонки/хабы (реальный разговор через колонку),
  - прием/озвучивание **SMS** на умных колонках/панелях.

- **Умный дом → телеком**
  - инициирование телеком-действий по событиям устройств (датчик дыма, домофон, браслет): звонки, SMS, эскалации.

### 1.2. Целевые экосистемы
1) **OEM-устройства оператора** (обязательный режим):  
   - OEM Voice Hub/колонка как **SIP/WebRTC endpoint**, регистрируется в Kamailio, участвует в параллельном вызове и в разговоре.

2) **Яндекс** (подтверждено наличие **voice-call API**):  
   - звонок на Яндекс.Станцию должен обеспечивать **двусторонний разговор**,
   - реализуется через выделенный шлюз **Yandex Voice Gateway (YVG)**, который транслирует SIP↔Yandex API.

### 1.3. Обязательные сценарии (MVP)
- **Входящий вызов**: параллельный дозвон на:
  - телефон абонента (hairpin через IMS),
  - OEM Hub/колонку,
  - Яндекс-колонку (через YVG).
  Побеждает первый ответивший, остальные ветки отменяются (CANCEL).

- **Входящий SMS**: доставка в умный дом (TTS/notification) по политикам приватности.

- **События умного дома**: датчик дыма/домофон/браслет → сценарий обзвона + SMS + эскалации.

---

## 2. Исходные вводные по платформе (as-is)

- **SIP signaling path:** `IMS/PSTN → Kamailio → FreeSWITCH`
- **B2BUA:** выполняется на **FreeSWITCH**
- **Control/Service logic:** TAS управляет логикой через **ESL** (и/или dialplan)
- **DB:** PostgreSQL
- **WebRTC (OEM):** опционально
- **SIP/TLS (OEM):** опционально (вторая опция, обязательна к поддержке)

---

## 3. Архитектура (to-be)

### 3.1. Логическая схема

```text
   IMS/PSTN/SMSC
        |
        v
     Kamailio (edge/proxy/registrar, TLS/WSS, rate-limit)
        |
        v
   FreeSWITCH (B2BUA: bridge/fork/media/IVR/TTS)
        ^
        | ESL events/commands
        |
       TAS  --------------------->  IIM (Policy/Registry/Rules/Connectors)
                                      |             |
                                      |             +--> OEM Connector (provisioning, device state)
                                      |
                                      +--> Yandex Voice Gateway (YVG): SIP trunk ↔ Yandex voice-call API
```

### 3.2. Компоненты IIM (конкретизация)

**Core**
- `IIM-Policy/Lookup Service` — выдача плана параллельного вызова (legs), таймаутов, политики.
- `IIM-Registry Service` — абоненты/дома/устройства/привязки/capabilities.
- `IIM-Consent & Privacy` — согласия и приватность (озвучивание, входящие, health-события).
- `IIM-Rules Engine` — триггеры IoT → телеком-действия (обзвон/смс/эскалации), дедупликация.
- `IIM-Audit/Observability` — аудит действий, метрики, трассировка.

**Connectors**
- `IIM-OEM Connector` — provisioning OEM Hub (SIP/TLS или WebRTC), webhooks/MQTT событий OEM.
- `IIM-Yandex Connector` — учетные привязки/токены, управление устройствами.
- `Yandex Voice Gateway (YVG)` — SIP trunk для FreeSWITCH + интеграция с Yandex voice-call API.

**Adapters к телеком**
- `IIM-FreeSWITCH Adapter (ESL)` — опционально, если часть логики оркестрации вынесена из dialplan в TAS/IIM.
- `IIM-SMS Adapter` — SMPP/HTTP к SMSC.

---

## 4. Принципы реализации параллельного вызова

### 4.1. Общая модель
Параллельный вызов реализуется на FreeSWITCH (B2BUA) как “hairpin”:

- A-leg: входящий вызов абоненту (caller → платформа)
- B-leg #1: исходящий на телефон абонента через IMS (hairpin)
- B-leg #2: исходящий на OEM Hub endpoint (SIP/TLS или WebRTC)
- B-leg #3: исходящий на Яндекс endpoint через YVG (SIP trunk)

**Победитель:** первый ответивший B-leg.  
**Проигравшие ветки:** должны получить CANCEL (важно для прекращения звонка на колонках).

### 4.2. Предотвращение петли hairpin
B-leg #1 (на MSISDN) не должен снова попадать в сервисную логику (иначе loop).  
Решение:
- добавлять на hairpin INVITE заголовок:
  - `X-Service-Bypass: parallel-ring`
- в Kamailio проверять этот заголовок и маршрутизировать **напрямую в IMS**, минуя сервис.

---

## 5. API-контракты

### 5.1. TAS → IIM: lookup для входящего вызова

**Endpoint:** `POST /v1/telephony/incoming/lookup`

**Request:**
```json
{
  "tenant_id": "op-ru",
  "call": {
    "call_id": "uuid-or-correlation-id",
    "from": "+79991234567",
    "to": "+74951234567",
    "sip_call_id": "a84b4c76e66710@ims",
    "source": "ims-trunk-1",
    "time_utc": "2026-02-03T17:51:56Z"
  },
  "capabilities": {
    "oem_webrtc_allowed": true,
    "oem_sip_tls_allowed": true,
    "yandex_voice_allowed": true
  }
}
```

**Response (leg plan):**
```json
{
  "decision_id": "dec-2c0c6c9a",
  "subscriber_id": "sub-123",
  "policy": {
    "ring_timeout_sec": 25,
    "parallel_ring": true,
    "cancel_others_on_answer": true,
    "ignore_early_media": true
  },
  "legs": [
    {
      "leg_id": "phone",
      "kind": "ims_mobile",
      "fs_endpoint": "sofia/gateway/ims/+74951234567",
      "fs_vars": {
        "sip_h_X-Service-Bypass": "parallel-ring",
        "sip_h_Diversion": "<sip:+74951234567@operator>;reason=unconditional"
      }
    },
    {
      "leg_id": "oemhub",
      "kind": "oem_endpoint",
      "fs_endpoint": "sofia/external/sip:oemhub-8a12@home.op.example;transport=tls",
      "fs_vars": {
        "rtp_secure_media": "mandatory",
        "sip_h_X-IoT-DeviceId": "oemhub-8a12"
      }
    },
    {
      "leg_id": "yandex",
      "kind": "yandex_voice",
      "fs_endpoint": "sofia/gateway/yandex_voice/station-xyz",
      "fs_vars": {
        "rtp_secure_media": "mandatory",
        "sip_h_X-IoT-DeviceId": "yandex-station-xyz"
      }
    }
  ]
}
```

### 5.2. FS/TAS → IIM: события по вызову (для аудита/аналитики)
**Endpoint:** `POST /v1/telephony/calls/{call_id}/events`

**Payload (пример):**
```json
{
  "event": "LEG_ANSWERED",
  "time_utc": "2026-02-03T17:46:02Z",
  "leg_id": "oemhub",
  "fs_uuid": "b3f2c9c8-...-9aa1",
  "sip": {
    "remote_user_agent": "OEMVoiceHub/1.4",
    "srtp": true
  }
}
```

---

## 6. Kamailio: требования и ключевые правила маршрутизации

### 6.1. Входящий INVITE из IMS → FreeSWITCH
- Все inbound INVITE (кроме bypass) направлять в FreeSWITCH B2BUA.
- Проставлять корреляцию `X-Correlation-ID: $ci`.

### 6.2. Bypass hairpin на MSISDN (к IMS)
**Требование:** если INVITE содержит `X-Service-Bypass: parallel-ring`, отправлять в IMS/trunk без применения сервисной логики.

Пример логики (фрагмент, концепт):
```cfg
if (is_method("INVITE") && $hdr(X-Service-Bypass) == "parallel-ring") {
    route(TO_IMS);
    exit;
}
```

### 6.3. Регистрация OEM Hub (SIP/TLS и WebRTC/WSS)
- Поддержать:
  - SIP REGISTER over TLS
  - SIP over WSS (WebRTC signaling) как опция
- Требования безопасности:
  - обязательная аутентификация,
  - rate-limit REGISTER/INVITE,
  - ACL по tenant/realm,
  - запрет открытых релеев и слабых cipher suites.

> Для WebRTC может понадобиться RTPengine для ICE/DTLS/NAT traversal — определяется выбранной схемой медиа-терминации.

---

## 7. FreeSWITCH: реализация параллельного вызова (B2BUA)

### 7.1. Общие настройки на A-leg
- `hangup_after_bridge=true`
- `continue_on_fail=true`
- `ignore_early_media=true` (ключевой параметр)
- `call_timeout=<policy>` (например 25 сек)
- общий ringback централизованно на A-leg (по необходимости)

### 7.2. Реализация через dialplan (рекомендуемый базовый вариант)

#### 7.2.1. Dialplan XML (контекст `from_kamailio`)
```xml
<extension name="inbound_to_parallel_ring">
  <condition field="destination_number" expression="^(\+7\d{10})$">
    <action application="set" data="hangup_after_bridge=true"/>
    <action application="set" data="continue_on_fail=true"/>
    <action application="set" data="ignore_early_media=true"/>
    <action application="set" data="call_timeout=25"/>
    <action application="export" data="call_id=${uuid}"/>
    <action application="lua" data="iim_lookup_and_bridge.lua"/>
  </condition>
</extension>
```

#### 7.2.2. Lua-скрипт (каркас)
> В реальной поставке заменить `system curl` на безопасный HTTP клиент (`mod_curl`/Lua HTTP), добавить mTLS/токены, JSON parse.

```lua
-- iim_lookup_and_bridge.lua (каркас)

local api = freeswitch.API()
local session_uuid = session:get_uuid()

local to = session:getVariable("destination_number")
local from = session:getVariable("caller_id_number")
local sip_call_id = session:getVariable("sip_call_id") or ""

-- TODO: HTTP POST в IIM /lookup и JSON parse legs
local legs = {
  {
    endpoint = "sofia/gateway/ims/" .. to,
    vars = {
      ["sip_h_X-Service-Bypass"] = "parallel-ring",
      ["sip_h_Diversion"] = "<sip:"..to.."@operator>;reason=unconditional"
    }
  },
  {
    endpoint = "sofia/external/sip:oemhub-8a12@home.op.example;transport=tls",
    vars = { ["rtp_secure_media"] = "mandatory" }
  },
  {
    endpoint = "sofia/gateway/yandex_voice/station-xyz",
    vars = { ["rtp_secure_media"] = "mandatory" }
  }
}

local function encode_vars(v)
  local parts = {}
  for k,val in pairs(v) do
    table.insert(parts, k .. "=" .. tostring(val))
  end
  return "{" .. table.concat(parts, ",") .. "}"
end

local dial_parts = {}
for _,leg in ipairs(legs) do
  table.insert(dial_parts, "[" .. encode_vars(leg.vars) .. "]" .. leg.endpoint)
end

local dialstring = table.concat(dial_parts, "|")
session:execute("bridge", dialstring)
```

### 7.3. Реализация через ESL (если TAS оркестрирует параллельный дозвон)
#### 7.3.1. Подписка на события
```text
event plain CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP_COMPLETE CHANNEL_BRIDGE
```

#### 7.3.2. Управление вызовом
```text
uuid_setvar <A_UUID> hangup_after_bridge true
uuid_setvar <A_UUID> continue_on_fail true
uuid_setvar <A_UUID> ignore_early_media true
uuid_setvar <A_UUID> call_timeout 25

uuid_transfer <A_UUID> -both 'bridge:
[{sip_h_X-Service-Bypass=parallel-ring}]sofia/gateway/ims/+74951234567|
[{rtp_secure_media=mandatory}]sofia/external/sip:oemhub-8a12@home.op.example;transport=tls|
[{rtp_secure_media=mandatory}]sofia/gateway/yandex_voice/station-xyz
' inline
```

---

## 8. OEM Hub: provisioning, регистрация, режимы SIP/TLS и WebRTC

### 8.1. Архитектурные требования к OEM Hub
- Должен выступать как:
  - SIP UA (TLS + SRTP) **и/или**
  - WebRTC endpoint (WSS + DTLS-SRTP + ICE) — опционально.
- Всегда-online профиль, поддержка входящих вызовов, корректная обработка CANCEL.

### 8.2. Provisioning API (IIM-OEM Connector)
**Endpoint:** `POST /v1/oem/provisioning/bootstrap` (mTLS + device attestation)

```json
{
  "device_sn": "OEM-VA-00001234",
  "device_model": "VoiceHub v2",
  "fw_version": "2.1.7",
  "attestation": {
    "type": "x509",
    "cert_chain": "-----BEGIN CERTIFICATE-----..."
  }
}
```

**Response (пример):**
```json
{
  "device_id": "oemhub-8a12",
  "sip": {
    "aor": "oemhub-8a12@home.op.example",
    "username": "oemhub-8a12",
    "password_ref": "kms://secrets/sip/oemhub-8a12",
    "registrar": "sip:home.op.example;transport=tls",
    "outbound_proxy": "sip:edge1.op.example;transport=tls",
    "require_srtp": true
  },
  "policy": {
    "max_parallel_calls": 1
  }
}
```

**Требование:** секреты не хранить и не отдавать в plaintext; использовать KMS/secret store, short-lived tokens, привязку к attestation.

---

## 9. Яндекс: реализация реального разговора через колонку

### 9.1. Общая идея
FreeSWITCH должен видеть Яндекс-колонку как **обычный B-leg** через SIP trunk.  
Все детали Yandex voice-call API изолируются в сервисе **Yandex Voice Gateway (YVG)**.

### 9.2. Контракт FS ↔ YVG (SIP trunk)
- SIP/TLS (желательно mTLS)
- SRTP mandatory
- Routing:
  - `sofia/gateway/yandex_voice/station-xyz`  
  - или URI: `sip:station-xyz@yvg.voice.op.example`

**Runtime:**
- INVITE → YVG вызывает Yandex voice-call API “ring device”
- Answer → YVG отдает 200 OK, медиа идет через YVG (anchored)
- CANCEL → YVG отменяет звонок в Яндекс

### 9.3. Требования к YVG
- Высокая надежность, stateful по звонкам
- CPS/конкурентные лимиты
- SLA по ring/answer событиям
- Журналирование и корреляция по `X-Correlation-ID`

---

## 10. Сценарии умного дома → телеком (обратные)

### 10.1. Примеры сценариев
- **Smoke/CO sensor**
  - немедленный звонок владельцу + SMS
  - при отсутствии ответа — эскалация (второй контакт/служба)
  - дедупликация, защита от флудинга

- **Домофон**
  - параллельный вызов: телефон + OEM + Яндекс
  - при no-answer — запись сообщения/уведомление

- **Браслет (fall/heart)**
  - IVR “подтвердите, нужна ли помощь”
  - эскалация по списку доверенных

### 10.2. Требования к rules engine
- Идемпотентность по `event_id`
- Дедупликация (окно времени)
- Throttling на тип события/устройство
- Эскалации и таймеры

---

## 11. Модель данных (PostgreSQL)

Минимальные сущности:
- `tenant`, `brand/region`
- `subscriber` (MSISDN, internal id)
- `household/location`
- `device` (oem/yandex, type, capabilities, ids)
- `binding` (subscriber↔household↔device)
- `consent` (scopes, validity, revocation)
- `policy` (quiet hours, allowlist senders, ring strategy)
- `scenario/rule` (trigger→actions→escalation)
- `credential_ref` (ссылки на секреты/токены в secret store)
- `audit_log` (append-only)

---

## 12. Нефункциональные требования (NFR)

### 12.1. Производительность
- Lookup IIM на входящий вызов: добавленная задержка не более 50–100 мс (при кешировании).
- Старт параллельного дозвона после входящего INVITE: не более 1–2 сек (без учета установления вызова).

### 12.2. Надежность
- HA для IIM и YVG (N+1)
- Очереди/шина событий (рекомендовано) для IoT сценариев
- Деградации:
  - если YVG недоступен → параллельный вызов без Яндекс ветки
  - если OEM недоступен → без OEM ветки

### 12.3. Observability
- Метрики: success rate дозвона по legs, ring/answer latency, cancel latency, ошибки SIP/TLS/SRTP, ошибки Yandex API.
- Логи с корреляцией: `call_id`, `decision_id`, `sip_call_id`.
- Аудит: все изменения consent/policy, все действия сценариев.

---

## 13. Безопасность

### 13.1. Ключевые угрозы
- Подмена IoT событий (ложный “дым” → массовый обзвон)
- Кража токенов Яндекс (контроль над устройствами/звонками)
- Несанкционированное озвучивание/доступ к SMS
- SIP атаки: registration hijack, toll fraud, INVITE flood
- DDoS на публичные endpoints IIM/YVG

### 13.2. Меры защиты

**Transport**
- TLS 1.2+ (предпочтительно 1.3), строгие cipher suites
- mTLS:
  - IIM ingress (OEM webhooks/devices)
  - FS↔YVG (рекомендовано)
- SRTP mandatory для веток на OEM и Яндекс

**Identity & Access**
- OAuth2/OIDC для внешних интеграций, short-lived access tokens
- RBAC для админ/операторских API
- Секреты: только в secret store/KMS, ротация, аудит доступа

**Anti-fraud**
- Whitelist направлений для IoT-инициированных исходящих вызовов
- Лимиты на CPS/минуты/число параллельных вызовов
- Детект аномалий (частые тревоги, необычные направления)

**Consent/Privacy**
- Явное согласие:
  - на прием входящих на колонку
  - на озвучивание SMS
- Политики “private mode” (без caller-id озвучивания), quiet hours, allowlist отправителей

**Input validation**
- Подпись событий (JWS/HMAC), timestamp+nonce (anti-replay)
- JSON schema validation
- Дедупликация и throttling IoT событий

---

## 14. Порядок внедрения (этапы)

### 14.1. Этап 1 (MVP: OEM + Яндекс Voice через YVG)
- Реестр и binding устройств (OEM/Yandex)
- Lookup API и параллельный дозвон (FS bridge `|`)
- YVG как SIP trunk + базовая интеграция с Yandex voice-call API
- Consent/policy минимум (включение/выключение звонка на колонки)
- Наблюдаемость и аудит базовые

### 14.2. Этап 2 (расширения)
- WebRTC для OEM Hub (WSS/ICE) + RTPengine (если нужно)
- Расширенный rules engine (эскалации, presence, room-based routing)
- SMS TTS на колонки и multi-device стратегии
- Anti-fraud скоринг, self-care UI

---

## 15. Открытые вопросы (для финализации дизайна)

1) Hairpin на MSISDN: точный dialstring IMS gateway, требования по PAI/Diversion/History-Info.
2) WebRTC терминация: Kamailio+RTPengine или FreeSWITCH end-to-end (DTLS/ICE).
3) Yandex voice-call API: модель медиа (anchored в YVG или direct), обязательные кодеки (opus), event callbacks.
4) Политики: сколько колонок форкать (все/главная/по комнате), управление presence.

---

## Приложение A. Рекомендованные параметры FreeSWITCH для качества

- `ignore_early_media=true`
- `leg_timeout=<policy>`
- `call_timeout=<policy>`
- `rtp_secure_media=mandatory` (OEM/Yandex)
- ограничение кодеков на legs (opus/pcmu), запрет небезопасных

---

## Приложение B. Рекомендованный заголовок bypass для Kamailio

- `X-Service-Bypass: parallel-ring`

**Требование:** Kamailio должен распознавать и маршрутизировать такие INVITE напрямую в IMS, минуя сервисную обработку.
## Дополнение к техдокументу (Part 2): детализация реализации, последовательности SIP/ESL, конфигурационные шаблоны, тесты

Ниже — продолжение/расширение ранее сформированного markdown-документа. Можно вставить как разделы **16+** и приложения.

---

## 16. Детальные последовательности вызовов (SIP/ESL)

### 16.1. Входящий звонок: параллельный дозвон (Phone + OEM + Yandex)

**Предусловия:**
- Inbound INVITE приходит в **Kamailio** с IMS и проксируется в **FreeSWITCH** (B2BUA).
- FreeSWITCH получает из IIM список legs (lookup).
- Для Yandex используется trunk на **YVG**.

**Последовательность (логическая):**
1. IMS → Kamailio: `INVITE (to=MSISDN)`
2. Kamailio → FreeSWITCH: `INVITE`
3. FreeSWITCH:
   - вызывает IIM `/lookup`
   - стартует `bridge` с `|` (параллельные legs)
4. FreeSWITCH → IMS (hairpin leg): `INVITE` (с `X-Service-Bypass: parallel-ring`)
5. FreeSWITCH → Kamailio → OEM Hub: `INVITE` (SRTP mandatory)
6. FreeSWITCH → YVG: `INVITE sip:station-xyz@...` (TLS+SRTP)
7. Первый ответивший leg возвращает `200 OK`
8. FreeSWITCH подтверждает `ACK`, соединяет с A-leg
9. FreeSWITCH отправляет `CANCEL` на оставшиеся ветки (и/или завершает их стандартным способом)
10. TAS/IIM получают события по ESL (ответившая ветка, отменённые ветки, причины)

### 16.2. Победа Yandex leg и отмена других
- FS получает `200 OK` от YVG раньше IMS/OEM
- FS:
  - бриджит A-leg ↔ Yandex leg
  - отправляет `CANCEL` в IMS (hairpin) и OEM leg
- Kamailio должен корректно пропустить CANCEL к OEM Hub

### 16.3. Обязательные ESL-события для корреляции (TAS слушает)
- `CHANNEL_CREATE` (A-leg)
- `CHANNEL_ANSWER` (по leg’ам, если используете originate+park)
- `CHANNEL_BRIDGE` (факт соединения A↔B)
- `CHANNEL_HANGUP_COMPLETE` (с причинами)
- `CHANNEL_DESTROY`

---

## 17. Стейт-машина вызова в IIM (минимум)

IIM хранит **не медиа-состояние**, а управляющее и аудиторское:

**Состояния (пример):**
- `NEW` → `LOOKUP_DONE` → `RINGING` → `BRIDGED(leg_id)` → `ENDED`

**События:**
- `INCOMING_CALL_SEEN`
- `LOOKUP_RETURNED`
- `LEG_RINGING` (опционально)
- `LEG_ANSWERED`
- `LEGS_CANCELLED`
- `CALL_ENDED`

**Требования:**
- Идемпотентность по `(tenant_id, call_id, event_type, leg_id, seq)`  
- TTL на записи вызова (например 24–72 часа) + агрегаты в аналитике

---

## 18. Реализация на FreeSWITCH: два “канонических” варианта

### 18.1. Вариант A (рекоменд. для MVP): `bridge` с параллельными legs (`|`)
**Плюсы:** простота, минимальный код, FS сам отменяет остальные legs.  
**Минусы:** сложнее тонко управлять каждой веткой (но обычно достаточно).

**Dialstring шаблон:**
```text
bridge:
[{leg_timeout=25,ignore_early_media=true,sip_h_X-Service-Bypass=parallel-ring}]sofia/gateway/ims/+74951234567|
[{leg_timeout=25,rtp_secure_media=mandatory}]sofia/external/sip:oemhub-8a12@home.op.example;transport=tls|
[{leg_timeout=25,rtp_secure_media=mandatory}]sofia/gateway/yandex_voice/station-xyz
```

### 18.2. Вариант B (для advanced контроля): `originate &park()` + `uuid_bridge`
**Плюсы:** полный контроль: можно “задушить” early media, точно отменять/перезапускать legs, добавлять условия.  
**Минусы:** больше логики в TAS/ESL, больше точек отказа.

**Шаблон ESL:**
```text
bgapi originate {origination_uuid=<B_IMS>,leg_timeout=25,sip_h_X-Service-Bypass=parallel-ring}sofia/gateway/ims/+74951234567 &park()
bgapi originate {origination_uuid=<B_OEM>,leg_timeout=25,rtp_secure_media=mandatory}sofia/external/sip:oemhub-8a12@home.op.example;transport=tls &park()
bgapi originate {origination_uuid=<B_YDX>,leg_timeout=25,rtp_secure_media=mandatory}sofia/gateway/yandex_voice/station-xyz &park()

# на первом CHANNEL_ANSWER:
uuid_bridge <A_UUID> <B_WINNER>
uuid_kill <B_LOSER1> ORIGINATOR_CANCEL
uuid_kill <B_LOSER2> ORIGINATOR_CANCEL
```

---

## 19. Kamailio: “скелет” конфигурации под bypass, маршрутизацию в FS и OEM registrations

> Это **не полный** `kamailio.cfg`, а ключевые идеи, которые должны быть отражены в вашем production-конфиге.

### 19.1. Bypass hairpin на IMS
```cfg
route[HANDLE_BYPASS] {
    if (is_method("INVITE") && $hdr(X-Service-Bypass) == "parallel-ring") {
        # отправить в IMS (dispatcher / static gw)
        route(TO_IMS);
        exit;
    }
}
```

### 19.2. IMS → FreeSWITCH
```cfg
route[FROM_IMS] {
    route(HANDLE_BYPASS);

    if (is_method("INVITE")) {
        append_hf("X-Correlation-ID: $ci\r\n");
        $du = "sip:freeswitch-b2bua.op.example:5061;transport=tls";
        t_relay();
        exit;
    }
}
```

### 19.3. OEM registrar (TLS) и WebRTC (WSS) — требования
- TLS-only для SIP UA (OEM SIP/TLS)
- WSS для WebRTC signaling (опционально)
- auth mandatory
- rate-limits на REGISTER/INVITE
- отдельный realm/домен для OEM, чтобы не смешивать с публичной сигнализацией

---

## 20. Yandex Voice Gateway (YVG): требования, интерфейсы и SIP-мэппинг

### 20.1. Роль YVG
YVG — **медиа/сигнализационный якорь** между FreeSWITCH и Yandex voice-call API:
- наружу (к FS): SIP/TLS + SRTP trunk
- внутрь (к Яндексу): API для “ring/answer/hangup”, плюс медиа-канал (обычно WebRTC/SRTP)

### 20.2. Функциональные требования к YVG
- `INVITE station-xyz`:
  - верифицировать tenant/ACL
  - найти binding `station-xyz → yandex_device_id`
  - создать сессию в Yandex API
  - вернуть `180 Ringing` в FS
- при “answer” на стороне Яндекса:
  - вернуть `200 OK` в FS (SDP согласован)
- при `CANCEL`/`BYE` от FS:
  - вызвать cancel/hangup в Yandex API
- события/метрики:
  - ring time, answer time, fail reason, API errors, SRTP status

### 20.3. Безопасность YVG
- mTLS FS↔YVG
- SRTP mandatory
- ограничения по CPS/конкурентности
- строгая валидация R-URI (разрешены только `station-*` форматы)

---

## 21. Улучшение реализации lookup в FreeSWITCH (без shell `curl`)

### 21.1. Требование
В production нельзя делать `system curl` из dialplan-скрипта из-за:
- безопасности (shell injection),
- производительности,
- наблюдаемости.

### 21.2. Рекомендации
- использовать `mod_curl` (если доступен) или HTTP клиент в Lua;
- включить mTLS/подписи между FS↔IIM или проксировать lookup через TAS.

---

## 22. Политики выбора OEM режима (SIP/TLS vs WebRTC)

IIM должен возвращать endpoint в зависимости от capability и состояния:

**Алгоритм (пример):**
1. Если есть активный WebRTC registration и качество канала ok → использовать WebRTC.
2. Иначе SIP/TLS registration → использовать SIP/TLS.
3. Иначе OEM leg не включать.

**В lookup response** это отражается через `fs_endpoint` и `fs_vars` (например кодеки `opus` предпочтительно для WebRTC).

---

## 23. Набор метрик и алертов (минимум)

### 23.1. Метрики параллельного вызова
- `parallel_ring_attempt_total{leg_kind=ims|oem|yandex}`
- `parallel_ring_answer_total{leg_kind=...}`
- `parallel_ring_cancel_total{leg_kind=...}`
- `parallel_ring_setup_latency_ms{leg_kind=...}` (INVITE→180, INVITE→200)
- `winner_leg_share{leg_kind=...}`

### 23.2. Алерты
- рост `yvg_api_error_rate` выше порога
- `cancel_latency_ms` слишком высокий (колонки продолжают звонить)
- падение регистрации OEM устройств
- аномально высокий CPS на bypass hairpin (признак лупа/фрода)

---

## 24. План тестирования (приемочные тесты)

### 24.1. Функциональные
1. **Параллельный вызов**: входящий → ring на phone+OEM+Yandex.
2. **Победа phone**: ответ на телефоне → колонка OEM и Яндекс прекращают звонить (CANCEL).
3. **Победа OEM**: ответ на колонке OEM → phone и Яндекс прекращают звонить.
4. **Победа Yandex**: ответ на Станции → phone и OEM прекращают звонить.
5. **No-answer**: никто не ответил за 25 сек → корректный финальный сценарий (voicemail/сброс/переадресация).
6. **YVG down**: Яндекс ветка не поднимается → остаются phone+OEM, вызов успешен.
7. **OEM offline**: OEM ветка не поднимается → остаются phone+Yandex.

### 24.2. Нагрузочные
- CPS на inbound (профиль)
- массовые параллельные вызовы (leg multiplication)
- деградация YVG (latency/ошибки) и влияние на общую задержку

### 24.3. Безопасность
- попытки loop без `X-Service-Bypass` (убедиться, что контроль есть)
- INVITE flood / REGISTER brute-force на OEM registrar
- replay атаки на IoT webhooks
- проверка, что SRTP mandatory реально enforced на legs

---

---
