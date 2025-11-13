# Таблица всех HAProxy API методов

## Сводная таблица методов

| Метод | Endpoint | Описание | Параметры |
|-------|----------|----------|-----------|
| **GET** | `/api/v1/haproxy/instances` | Получить список всех доступных HAProxy инстансов | - |
| **GET** | `/api/v1/haproxy/backends` | Получить список всех бэкендов (дефолтный инстанс) | - |
| **GET** | `/api/v1/haproxy/{instance}/backends` | Получить список бэкендов конкретного инстанса | `instance` - имя инстанса |
| **GET** | `/api/v1/haproxy/backends/{backend}/servers` | Получить список серверов в бэкенде (дефолтный инстанс) | `backend` - имя бэкенда |
| **GET** | `/api/v1/haproxy/{instance}/backends/{backend}/servers` | Получить список серверов в бэкенде конкретного инстанса | `instance` - имя инстанса<br>`backend` - имя бэкенда |
| **POST** | `/api/v1/haproxy/backends/{backend}/servers/{server}/action` | Изменить состояние сервера (дефолтный инстанс) | `backend` - имя бэкенда<br>`server` - имя сервера<br>`body.action` - ready/drain/maint |
| **POST** | `/api/v1/haproxy/{instance}/backends/{backend}/servers/{server}/action` | Изменить состояние сервера в конкретном инстансе | `instance` - имя инстанса<br>`backend` - имя бэкенда<br>`server` - имя сервера<br>`body.action` - ready/drain/maint |

## Быстрые примеры curl для всех методов

### GET запросы

```bash
# 1. Список всех доступных инстансов HAProxy
curl http://localhost:11011/api/v1/haproxy/instances

# 2. Список бэкендов (дефолтный инстанс)
curl http://localhost:11011/api/v1/haproxy/backends

# 3. Список бэкендов (инстанс prod)
curl http://localhost:11011/api/v1/haproxy/prod/backends

# 4. Серверы в бэкенде (дефолтный инстанс)
curl http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers

# 5. Серверы в бэкенде (инстанс staging)
curl http://localhost:11011/api/v1/haproxy/staging/backends/bn_api/servers
```

### POST запросы

```bash
# 5. Включить сервер (ready) - дефолтный инстанс
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'

# 6. Плавное отключение (drain) - инстанс prod
curl -X POST http://localhost:11011/api/v1/haproxy/prod/backends/bn_webapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'

# 7. Режим обслуживания (maint) - дефолтный инстанс
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "maint"}'
```

## Состояния серверов

| Состояние | Описание | Использование |
|-----------|----------|---------------|
| **UP** | Сервер активен и принимает трафик | Нормальная работа |
| **DRAIN** | Сервер не принимает новые соединения, завершает существующие | Плавное отключение для обслуживания |
| **MAINT** | Сервер в режиме обслуживания, недоступен | Полное отключение для обслуживания |
| **DOWN** | Сервер недоступен (не проходит health check) | Проблема с сервером |

## Действия (actions)

| Action | Команда HAProxy | Результат | Когда использовать |
|--------|-----------------|-----------|-------------------|
| **ready** | `set server {backend}/{server} state ready` | Сервер переводится в состояние UP | После завершения обслуживания |
| **drain** | `set server {backend}/{server} state drain` | Сервер переводится в состояние DRAIN | Перед плановым обслуживанием |
| **maint** | `set server {backend}/{server} state maint` | Сервер переводится в состояние MAINT | Для аварийного отключения |

## Полезные однострочники

```bash
# Количество активных серверов в бэкенде
curl -s http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers | \
  jq '[.data.servers[] | select(.status == "UP")] | length'

# Список всех серверов не в состоянии UP
curl -s http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers | \
  jq '.data.servers[] | select(.status != "UP") | {name, status}'

# Проверка конкретного сервера
curl -s http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers | \
  jq '.data.servers[] | select(.name == "srv01_app1") | .status'

# Список всех бэкендов всех инстансов
for inst in default prod staging; do
  echo "Instance: $inst"
  curl -s http://localhost:11011/api/v1/haproxy/$inst/backends 2>/dev/null | \
    jq -r '.data.backends[]' 2>/dev/null || echo "  not available"
done

# Массовое включение всех серверов
BACKEND="bn_webapp"
curl -s http://localhost:11011/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status != "UP") | .name' | \
  while read server; do
    curl -X POST http://localhost:11011/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
      -H "Content-Type: application/json" -d '{"action": "ready"}'
  done

# Статистика по всем бэкендам
curl -s http://localhost:11011/api/v1/haproxy/backends | jq -r '.data.backends[]' | \
  while read backend; do
    echo -n "$backend: "
    curl -s http://localhost:11011/api/v1/haproxy/backends/$backend/servers | \
      jq -r '[.data.servers[] | .status] | group_by(.) | map("\(.[0])=\(length)") | join(", ")'
  done
```

## Конфигурация

### Переменные окружения для HAProxy

```bash
# Единичный инстанс
export HAPROXY_SOCKET_PATH="/var/run/haproxy.sock"  # Unix socket
# или
export HAPROXY_SOCKET_PATH="ipv4@192.168.1.15:7777"  # TCP socket

# Множественные инстансы
export HAPROXY_INSTANCES="prod=/var/run/haproxy1.sock,staging=/var/run/haproxy2.sock,backup=ipv4@192.168.1.20:7777"

# Таймаут подключения (в секундах)
export HAPROXY_TIMEOUT="5.0"
```

## Файлы документации

- [HAPROXY_API.md](HAPROXY_API.md) - Основная документация HAProxy API с архитектурой
- [HAPROXY_API_REFERENCE.md](HAPROXY_API_REFERENCE.md) - Полный справочник с примерами и сценариями
- [HAPROXY_API_METHODS_TABLE.md](HAPROXY_API_METHODS_TABLE.md) - Данный файл со сводной таблицей