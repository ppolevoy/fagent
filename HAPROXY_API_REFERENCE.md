# HAProxy API - Полный справочник методов

## Оглавление

1. [Базовая информация](#базовая-информация)
2. [Методы API](#методы-api)
   - [GET методы](#get-методы)
   - [POST методы](#post-методы)
3. [Примеры использования](#примеры-использования)
4. [Сценарии использования](#сценарии-использования)
5. [Коды ошибок](#коды-ошибок)

## Базовая информация

### URL формат
```
http://{agent_host}:{agent_port}/api/v1/haproxy/{путь}
```

Где:
- `agent_host` - хост агента (по умолчанию: 0.0.0.0)
- `agent_port` - порт агента (по умолчанию: 11011)

### Формат ответов

#### Успешный ответ
```json
{
  "success": true,
  "status_code": 200,
  "data": { ... },
  "message": "Optional message"
}
```

#### Ошибка
```json
{
  "success": false,
  "status_code": 400|404|500|502|503,
  "error": "Error description"
}
```

## Методы API

### GET методы

#### 1. Получить список всех доступных HAProxy инстансов

**Метод:** `GET /api/v1/haproxy/instances`

**Описание:** Возвращает список всех настроенных HAProxy инстансов с информацией об их доступности.

**Пример curl:**
```bash
curl -X GET http://localhost:11011/api/v1/haproxy/instances
```

**Пример ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instances": [
      {
        "name": "default",
        "socket_path": "/var/run/haproxy.sock",
        "available": true
      },
      {
        "name": "prod",
        "socket_path": "/var/run/haproxy-prod.sock",
        "available": true
      },
      {
        "name": "staging",
        "socket_path": "ipv4@192.168.1.15:7777",
        "available": false
      }
    ],
    "count": 3
  }
}
```

#### 2. Получить список всех бэкендов (дефолтный инстанс)

**Метод:** `GET /api/v1/haproxy/backends`

**Описание:** Возвращает список всех бэкендов в дефолтном HAProxy инстансе.

**Пример curl:**
```bash
curl -X GET http://localhost:11011/api/v1/haproxy/backends
```

**Пример ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backends": ["bn_app1", "bn_app2", "bn_static"],
    "count": 3
  }
}
```

#### 3. Получить список бэкендов конкретного инстанса

**Метод:** `GET /api/v1/haproxy/{instance_name}/backends`

**Описание:** Возвращает список всех бэкендов в указанном HAProxy инстансе.

**Параметры:**
- `instance_name` - имя HAProxy инстанса (например: prod, staging)

**Примеры curl:**
```bash
# Инстанс prod
curl -X GET http://localhost:11011/api/v1/haproxy/prod/backends

# Инстанс staging
curl -X GET http://localhost:11011/api/v1/haproxy/staging/backends
```

**Пример ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "prod",
    "backends": ["bn_webapp", "bn_api", "bn_admin"],
    "count": 3
  }
}
```

#### 4. Получить список серверов в бэкенде (дефолтный инстанс)

**Метод:** `GET /api/v1/haproxy/backends/{backend_name}/servers`

**Описание:** Возвращает список всех серверов и их статусы в указанном бэкенде.

**Параметры:**
- `backend_name` - имя бэкенда

**Пример curl:**
```bash
curl -X GET http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers
```

**Пример ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backend": "bn_webapp",
    "servers": [
      {
        "name": "srv01_app1",
        "status": "UP",
        "weight": "1",
        "check_status": "L4OK",
        "check_duration": "0",
        "last_chg": "3600",
        "downtime": "0",
        "addr": "192.168.1.10:8080",
        "cookie": ""
      },
      {
        "name": "srv02_app1",
        "status": "DRAIN",
        "weight": "1",
        "check_status": "L4OK",
        "check_duration": "1",
        "last_chg": "120",
        "downtime": "0",
        "addr": "192.168.1.11:8080",
        "cookie": ""
      },
      {
        "name": "srv03_app1",
        "status": "MAINT",
        "weight": "1",
        "check_status": "L4OK",
        "check_duration": "0",
        "last_chg": "60",
        "downtime": "60",
        "addr": "192.168.1.12:8080",
        "cookie": ""
      }
    ],
    "count": 3
  }
}
```

#### 5. Получить список серверов в бэкенде конкретного инстанса

**Метод:** `GET /api/v1/haproxy/{instance_name}/backends/{backend_name}/servers`

**Описание:** Возвращает список всех серверов и их статусы в указанном бэкенде конкретного инстанса.

**Параметры:**
- `instance_name` - имя HAProxy инстанса
- `backend_name` - имя бэкенда

**Примеры curl:**
```bash
# Серверы в бэкенде bn_webapp инстанса prod
curl -X GET http://localhost:11011/api/v1/haproxy/prod/backends/bn_webapp/servers

# Серверы в бэкенде bn_api инстанса staging
curl -X GET http://localhost:11011/api/v1/haproxy/staging/backends/bn_api/servers
```

### POST методы

#### 6. Изменить состояние сервера (дефолтный инстанс)

**Метод:** `POST /api/v1/haproxy/backends/{backend_name}/servers/{server_name}/action`

**Описание:** Изменяет состояние сервера в HAProxy.

**Параметры:**
- `backend_name` - имя бэкенда
- `server_name` - имя сервера

**Body:**
```json
{
  "action": "ready|drain|maint"
}
```

**Допустимые значения action:**
- `ready` - Включить сервер (готов принимать трафик)
- `drain` - Плавное отключение (не принимает новые соединения, завершает существующие)
- `maint` - Режим обслуживания (сервер полностью недоступен)

**Примеры curl:**

```bash
# Включить сервер (ready)
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01_app1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'

# Плавное отключение сервера (drain)
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01_app1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'

# Перевести в режим обслуживания (maint)
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01_app1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "maint"}'
```

**Пример успешного ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backend": "bn_webapp",
    "server": "srv01_app1",
    "action": "drain",
    "status": "completed"
  },
  "message": "Server state successfully changed to 'drain'"
}
```

#### 7. Изменить состояние сервера в конкретном инстансе

**Метод:** `POST /api/v1/haproxy/{instance_name}/backends/{backend_name}/servers/{server_name}/action`

**Описание:** Изменяет состояние сервера в указанном HAProxy инстансе.

**Параметры:**
- `instance_name` - имя HAProxy инстанса
- `backend_name` - имя бэкенда
- `server_name` - имя сервера

**Примеры curl:**

```bash
# Включить сервер в инстансе prod
curl -X POST http://localhost:11011/api/v1/haproxy/prod/backends/bn_webapp/servers/srv01_app1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'

# Drain сервер в инстансе staging
curl -X POST http://localhost:11011/api/v1/haproxy/staging/backends/bn_api/servers/api_server_1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'

# Maintenance в инстансе backup
curl -X POST http://localhost:11011/api/v1/haproxy/backup/backends/bn_db/servers/db_replica_2/action \
  -H "Content-Type: application/json" \
  -d '{"action": "maint"}'
```

## Примеры использования

### Базовые операции

#### Проверка доступности API
```bash
# Health check агента
curl http://localhost:11011/ping

# Получить список обнаруженных приложений
curl http://localhost:11011/app
```

#### Получение информации о HAProxy
```bash
# Список всех бэкендов
curl http://localhost:11011/api/v1/haproxy/backends

# Информация о серверах в конкретном бэкенде
curl http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers
```

### Работа с форматированием вывода (jq)

#### Получить только имена бэкендов
```bash
curl -s http://localhost:11011/api/v1/haproxy/backends | jq -r '.data.backends[]'
```

#### Получить статусы серверов
```bash
curl -s http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers | \
  jq '.data.servers[] | {name: .name, status: .status}'
```

#### Получить только активные серверы
```bash
curl -s http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers | \
  jq '.data.servers[] | select(.status == "UP") | .name'
```

### Скрипты автоматизации

#### Проверка статуса всех серверов во всех бэкендах
```bash
#!/bin/bash
HOST="localhost:11011"

# Получаем список бэкендов
BACKENDS=$(curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]')

for backend in $BACKENDS; do
    echo "=== Backend: $backend ==="
    curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | \
      jq -r '.data.servers[] | "\(.name): \(.status)"'
    echo
done
```

#### Плавное отключение всех серверов в бэкенде
```bash
#!/bin/bash
HOST="localhost:11011"
BACKEND="bn_webapp"

# Получаем список серверов
SERVERS=$(curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status == "UP") | .name')

for server in $SERVERS; do
    echo "Draining server: $server"
    curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
      -H "Content-Type: application/json" \
      -d '{"action": "drain"}'
    echo
done
```

#### Включение всех серверов в режиме обслуживания
```bash
#!/bin/bash
HOST="localhost:11011"
BACKEND="bn_webapp"

# Получаем список серверов в MAINT
SERVERS=$(curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status == "MAINT") | .name')

for server in $SERVERS; do
    echo "Enabling server: $server"
    curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
      -H "Content-Type: application/json" \
      -d '{"action": "ready"}'
    echo
done
```

## Сценарии использования

### 1. Rolling Update (последовательное обновление)
```bash
#!/bin/bash
HOST="localhost:11011"
BACKEND="bn_webapp"

# Получаем все серверы
SERVERS=$(curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[].name')

for server in $SERVERS; do
    echo "Processing server: $server"

    # 1. Drain server
    echo "  - Draining..."
    curl -s -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
      -H "Content-Type: application/json" \
      -d '{"action": "drain"}' | jq -r '.message'

    # 2. Wait for connections to drain
    echo "  - Waiting 30 seconds for connections to drain..."
    sleep 30

    # 3. Perform maintenance (update, restart, etc.)
    echo "  - Performing maintenance..."
    # Your maintenance commands here
    sleep 5

    # 4. Enable server
    echo "  - Enabling..."
    curl -s -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
      -H "Content-Type: application/json" \
      -d '{"action": "ready"}' | jq -r '.message'

    # 5. Wait before next server
    echo "  - Waiting 10 seconds before next server..."
    sleep 10
    echo
done

echo "Rolling update completed!"
```

### 2. Blue-Green Deployment
```bash
#!/bin/bash
HOST="localhost:11011"
BACKEND="bn_webapp"

# Определяем группы серверов
BLUE_SERVERS="srv01_app1 srv02_app1"
GREEN_SERVERS="srv03_app1 srv04_app1"

echo "=== Blue-Green Deployment ==="

# 1. Проверяем текущий статус
echo "Current status:"
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | "\(.name): \(.status)"'
echo

# 2. Включаем GREEN группу
echo "Enabling GREEN servers..."
for server in $GREEN_SERVERS; do
    curl -s -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
      -H "Content-Type: application/json" \
      -d '{"action": "ready"}' | jq -r '.message'
done
echo

# 3. Ждем стабилизации
echo "Waiting for GREEN servers to stabilize (30 seconds)..."
sleep 30

# 4. Отключаем BLUE группу
echo "Draining BLUE servers..."
for server in $BLUE_SERVERS; do
    curl -s -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
      -H "Content-Type: application/json" \
      -d '{"action": "drain"}' | jq -r '.message'
done
echo

echo "Blue-Green deployment completed!"
```

### 3. Аварийное отключение сервера
```bash
#!/bin/bash
HOST="localhost:11011"
BACKEND="bn_webapp"
SERVER="srv01_app1"

echo "EMERGENCY: Immediately disabling server $SERVER"

# Немедленное отключение в maintenance mode
curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$SERVER/action \
  -H "Content-Type: application/json" \
  -d '{"action": "maint"}'

echo "Server $SERVER is now in maintenance mode"
```

### 4. Мониторинг состояния
```bash
#!/bin/bash
HOST="localhost:11011"

while true; do
    clear
    echo "=== HAProxy Server Status Monitor ==="
    echo "Time: $(date)"
    echo

    # Получаем все бэкенды
    BACKENDS=$(curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]')

    for backend in $BACKENDS; do
        echo "Backend: $backend"

        # Подсчитываем серверы по статусам
        STATS=$(curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | \
          jq -r '.data.servers | group_by(.status) | map({status: .[0].status, count: length}) | .[] | "  \(.status): \(.count)"')

        echo "$STATS"
        echo
    done

    sleep 5
done
```

### 5. Работа с множественными инстансами
```bash
#!/bin/bash
HOST="localhost:11011"
INSTANCES="prod staging backup"

echo "=== Multi-Instance Status Check ==="

for instance in $INSTANCES; do
    echo "Instance: $instance"

    # Получаем бэкенды для инстанса
    BACKENDS=$(curl -s http://$HOST/api/v1/haproxy/$instance/backends 2>/dev/null | jq -r '.data.backends[]' 2>/dev/null)

    if [ -z "$BACKENDS" ]; then
        echo "  - Instance not available or no backends"
    else
        for backend in $BACKENDS; do
            echo "  Backend: $backend"

            # Получаем статистику серверов
            UP_COUNT=$(curl -s http://$HOST/api/v1/haproxy/$instance/backends/$backend/servers | \
              jq '[.data.servers[] | select(.status == "UP")] | length')
            TOTAL_COUNT=$(curl -s http://$HOST/api/v1/haproxy/$instance/backends/$backend/servers | \
              jq '.data.servers | length')

            echo "    Active servers: $UP_COUNT/$TOTAL_COUNT"
        done
    fi
    echo
done
```

## Коды ошибок

### HTTP коды

| Код | Описание | Примеры |
|-----|----------|---------|
| 200 | Успешно | Операция выполнена успешно |
| 400 | Bad Request | Неверные параметры, невалидное действие |
| 404 | Not Found | Контроллер, бэкенд или сервер не найден |
| 500 | Internal Server Error | Внутренняя ошибка сервера |
| 502 | Bad Gateway | Ошибка выполнения команды HAProxy |
| 503 | Service Unavailable | HAProxy недоступен |

### Примеры ошибок

#### Неверное действие (400)
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "invalid_action"}'
```

Ответ:
```json
{
  "success": false,
  "status_code": 400,
  "error": "Invalid action 'invalid_action'. Allowed: ready, drain, maint"
}
```

#### Бэкенд не найден (404)
```bash
curl http://localhost:11011/api/v1/haproxy/backends/non_existent_backend/servers
```

Ответ:
```json
{
  "success": false,
  "status_code": 404,
  "error": "Backend 'non_existent_backend' not found"
}
```

#### HAProxy недоступен (503)
```json
{
  "success": false,
  "status_code": 503,
  "error": "HAProxy connection error: Socket file not found: /var/run/haproxy.sock"
}
```

## Дополнительные примеры

### Проверка здоровья HAProxy
```bash
#!/bin/bash
HOST="localhost:11011"

# Пытаемся получить список бэкендов
if curl -s -f http://$HOST/api/v1/haproxy/backends > /dev/null 2>&1; then
    echo "HAProxy API is healthy"
    exit 0
else
    echo "HAProxy API is not responding"
    exit 1
fi
```

### Экспорт конфигурации в JSON
```bash
#!/bin/bash
HOST="localhost:11011"

# Создаем JSON с полной конфигурацией
{
    echo "{"
    echo '  "timestamp": "'$(date -Iseconds)'",'
    echo '  "backends": ['

    BACKENDS=$(curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]')
    FIRST=true

    for backend in $BACKENDS; do
        if [ "$FIRST" = false ]; then
            echo ","
        fi
        FIRST=false

        echo "    {"
        echo '      "name": "'$backend'",'
        echo '      "servers": '
        curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | jq '.data.servers'
        echo -n "    }"
    done

    echo ""
    echo "  ]"
    echo "}"
} > haproxy_config_$(date +%Y%m%d_%H%M%S).json

echo "Configuration exported to haproxy_config_$(date +%Y%m%d_%H%M%S).json"
```

### Webhook интеграция
```bash
#!/bin/bash
HOST="localhost:11011"
WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Функция отправки уведомления
send_notification() {
    local message=$1
    curl -X POST $WEBHOOK_URL \
      -H "Content-Type: application/json" \
      -d "{\"text\": \"$message\"}"
}

# Мониторинг и уведомления
check_server_status() {
    local backend=$1
    local server=$2

    STATUS=$(curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | \
      jq -r ".data.servers[] | select(.name == \"$server\") | .status")

    if [ "$STATUS" != "UP" ]; then
        send_notification "⚠️ Server $server in backend $backend is $STATUS"
    fi
}

# Проверяем критические серверы
check_server_status "bn_webapp" "srv01_app1"
check_server_status "bn_api" "api_server_1"
```

## Тестирование API

### Простой тест всех методов
```bash
#!/bin/bash
HOST="localhost:11011"

echo "=== Testing HAProxy API ==="

# Test 1: Get backends
echo "Test 1: GET /api/v1/haproxy/backends"
curl -s http://$HOST/api/v1/haproxy/backends | jq '.success' | grep -q true && echo "✓ PASS" || echo "✗ FAIL"

# Test 2: Get invalid backend
echo "Test 2: GET /api/v1/haproxy/backends/invalid/servers (should fail)"
curl -s http://$HOST/api/v1/haproxy/backends/invalid/servers | jq '.success' | grep -q false && echo "✓ PASS" || echo "✗ FAIL"

# Test 3: Invalid action
echo "Test 3: POST with invalid action (should fail)"
curl -s -X POST http://$HOST/api/v1/haproxy/backends/test/servers/test/action \
  -H "Content-Type: application/json" \
  -d '{"action": "invalid"}' | jq '.success' | grep -q false && echo "✓ PASS" || echo "✗ FAIL"

echo "=== Tests completed ==="
```

## Заметки

- Все временные метки в ответах указаны в секундах
- Поле `weight` показывает вес сервера для балансировки нагрузки (обычно "1")
- Поле `last_chg` показывает время в секундах с последнего изменения статуса
- Поле `downtime` показывает общее время недоступности в секундах
- При использовании `drain` состояния, существующие соединения продолжают обрабатываться
- При использовании `maint` состояния, все соединения немедленно разрываются
- Рекомендуется использовать `drain` перед обслуживанием для плавного отключения

## См. также

- [HAPROXY_API.md](HAPROXY_API.md) - Основная документация HAProxy API
- [CLAUDE.md](CLAUDE.md) - Общая документация проекта
- [ROLLING_UPDATE_README.md](ROLLING_UPDATE_README.md) - Документация по rolling update