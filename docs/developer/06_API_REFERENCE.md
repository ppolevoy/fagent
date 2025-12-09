# API Reference

## Базовая информация

**Базовый URL:** `http://{host}:{port}`
**Порт по умолчанию:** `11011`
**Формат ответов:** JSON

---

## Общие endpoints

### Health Check

```
GET /ping
```

**Ответ:**
```json
{"status": "ok"}
```

**HTTP коды:**
- `200` - агент работает

---

### Список приложений

```
GET /app
GET /api/v1/apps
```

Возвращает все обнаруженные приложения, сгруппированные по источнику.

**Ответ:**
```json
{
  "server": {
    "name": "hostname",
    "ip": "192.168.1.1",
    "docker-app": {
      "applications": [
        {
          "container_id": "abc123...",
          "container_name": "my-app",
          "image": "registry/app",
          "tag": "v1.0.0",
          "ip": "192.168.1.1",
          "port": 8080,
          "status": "online",
          "pid": 12345,
          "start_time": "2025-01-01T00:00:00Z",
          "compose_project_dir": "/opt/docker/my-app",
          "eureka_registered": true,
          "eureka_instance_id": "192.168.1.1:my-app:8080",
          "eureka_app_name": "MY-APP",
          "eureka_status": "UP"
        }
      ],
      "count": 1,
      "last_update": "20250101_120000"
    },
    "site-app": {
      "applications": [
        {
          "name": "myapp",
          "version": "1.2.3",
          "status": "online",
          "start_time": "Oct_31",
          "pid": 54321,
          "port": 8080,
          "log_path": "/site/app/myapp/logs",
          "distr_path": "/site/share/htdoc/myapp-1.2.3.war",
          "artifact_size_bytes": 52428800,
          "artifact_size_mb": 50.0,
          "artifact_type": "war",
          "app_path": "/site/app/myapp"
        }
      ],
      "count": 1,
      "last_update": "20250101_120000"
    }
  }
}
```

---

## HAProxy API

### Список инстансов

```
GET /api/v1/haproxy/instances
```

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instances": [
      {"name": "default", "socket_path": "ipv4@192.168.1.1:7777", "available": true}
    ],
    "count": 1
  }
}
```

---

### Список бэкендов

```
GET /api/v1/haproxy/backends
GET /api/v1/haproxy/{instance}/backends
```

**Параметры:**
- `instance` (опционально) - имя HAProxy инстанса

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backends": ["bn_app1", "bn_app2"],
    "count": 2
  }
}
```

---

### Список серверов в бэкенде

```
GET /api/v1/haproxy/backends/{backend}/servers
GET /api/v1/haproxy/{instance}/backends/{backend}/servers
```

**Параметры:**
- `instance` (опционально) - имя HAProxy инстанса
- `backend` - имя бэкенда

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backend": "bn_app1",
    "servers": [
      {
        "name": "srv01_app1",
        "status": "UP",
        "weight": "100",
        "check_status": "L7OK",
        "check_duration": "5",
        "last_chg": "1234567",
        "downtime": "0",
        "addr": "192.168.1.10:8080",
        "cookie": ""
      }
    ],
    "count": 1
  }
}
```

---

### Изменение состояния сервера

```
POST /api/v1/haproxy/backends/{backend}/servers/{server}/action
POST /api/v1/haproxy/{instance}/backends/{backend}/servers/{server}/action
```

**Параметры:**
- `instance` (опционально) - имя HAProxy инстанса
- `backend` - имя бэкенда
- `server` - имя сервера

**Body:**
```json
{
  "action": "drain"
}
```

**Допустимые значения action:**
- `ready` - включить сервер
- `drain` - режим drain (не принимает новые соединения)
- `maint` - режим maintenance

**Ответ (успех):**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backend": "bn_app1",
    "server": "srv01_app1",
    "action": "drain",
    "status": "completed"
  },
  "message": "Server state successfully changed to 'drain'"
}
```

**Ответ (ошибка):**
```json
{
  "success": false,
  "status_code": 400,
  "error": "Invalid action 'invalid'. Allowed: ready, drain, maint"
}
```

---

## Eureka API

### Список приложений

```
GET /api/v1/eureka/apps
```

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "total": 5,
    "applications": [
      {
        "app_name": "MY-SERVICE",
        "instance_id": "192.168.1.100:my-service:8080",
        "ip": "192.168.1.100",
        "port": 8080,
        "home_page_url": "http://192.168.1.100:8080/",
        "status": "UP",
        "vip_address": "my-service",
        "health_check_url": "http://192.168.1.100:8080/actuator/health",
        "metadata": {}
      }
    ]
  }
}
```

---

### Информация о приложении

```
GET /api/v1/eureka/apps/{instance_id}
```

**Параметры:**
- `instance_id` - идентификатор инстанса (например: `192.168.1.100:my-service:8080`)

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "app_name": "MY-SERVICE",
    "instance_id": "192.168.1.100:my-service:8080",
    "ip": "192.168.1.100",
    "port": 8080,
    "status": "UP"
  }
}
```

---

### Health Check приложения

```
GET /api/v1/eureka/apps/{instance_id}/health
```

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance_id": "192.168.1.100:my-service:8080",
    "app_name": "MY-SERVICE",
    "health": {
      "status": "healthy",
      "http_status": 200,
      "health_status": "UP",
      "details": {
        "status": "UP",
        "components": {}
      }
    }
  }
}
```

---

### Pause приложения

```
POST /api/v1/eureka/apps/{instance_id}/pause
```

Отправляет POST запрос на `/actuator/pause` приложения.

**Ответ (успех):**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance_id": "192.168.1.100:my-service:8080",
    "app_name": "MY-SERVICE",
    "message": "Pause request sent successfully"
  }
}
```

---

### Shutdown приложения

```
POST /api/v1/eureka/apps/{instance_id}/shutdown
```

Отправляет POST запрос на `/actuator/shutdown` приложения для graceful shutdown.

**Ответ (успех):**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance_id": "192.168.1.100:my-service:8080",
    "app_name": "MY-SERVICE",
    "message": "Shutdown request sent successfully"
  }
}
```

---

### Изменение уровня логирования

```
POST /api/v1/eureka/apps/{instance_id}/loglevel
```

Изменяет уровень логирования через `/actuator/loggers`.

**Body:**
```json
{
  "logger": "ROOT",
  "level": "DEBUG"
}
```

**Параметры body:**
- `logger` - имя логгера (например: `ROOT`, `com.example.myapp`)
- `level` - уровень логирования: `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`, `OFF`

**Ответ (успех):**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance_id": "192.168.1.100:my-service:8080",
    "app_name": "MY-SERVICE",
    "logger": "ROOT",
    "level": "DEBUG",
    "message": "Log level for 'ROOT' changed to DEBUG"
  }
}
```

---

## Коды ответов

| Код | Описание |
|-----|----------|
| `200` | Успешное выполнение |
| `400` | Ошибка в запросе (неверные параметры, JSON) |
| `404` | Ресурс не найден (контроллер, бэкенд, сервер) |
| `405` | Метод не поддерживается |
| `500` | Внутренняя ошибка сервера |
| `502` | Ошибка выполнения команды (HAProxy) |
| `503` | Сервис недоступен (HAProxy не подключен, Eureka отключен) |

---

## Формат ошибок

Все ошибки возвращаются в едином формате:

```json
{
  "success": false,
  "status_code": 400,
  "error": "Описание ошибки"
}
```

---

## Примеры curl

### Health check
```bash
curl http://localhost:11011/ping
```

### Список приложений
```bash
curl http://localhost:11011/app
```

### Получить бэкенды HAProxy
```bash
curl http://localhost:11011/api/v1/haproxy/backends
```

### Получить серверы в бэкенде
```bash
curl http://localhost:11011/api/v1/haproxy/backends/bn_myapp/servers
```

### Drain сервер
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_myapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'
```

### Ready сервер
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_myapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'
```

### Eureka - список приложений
```bash
curl http://localhost:11011/api/v1/eureka/apps
```

### Eureka - health check приложения
```bash
curl http://localhost:11011/api/v1/eureka/apps/192.168.1.100:my-service:8080/health
```

### Eureka - shutdown приложения
```bash
curl -X POST http://localhost:11011/api/v1/eureka/apps/192.168.1.100:my-service:8080/shutdown
```

### Eureka - изменить log level
```bash
curl -X POST http://localhost:11011/api/v1/eureka/apps/192.168.1.100:my-service:8080/loglevel \
  -H "Content-Type: application/json" \
  -d '{"logger": "ROOT", "level": "DEBUG"}'
```
