# Контроллеры (Controllers)

## Обзор

Контроллеры предоставляют REST API для управления инфраструктурой. Каждый контроллер специализируется на своей подсистеме.

---

## HAProxyController

**Файл:** `controllers/haproxy_controller.py`

### Назначение

Управление состоянием серверов в HAProxy через Admin Socket. Поддерживает множественные инстансы HAProxy.

### Диаграмма класса

```
┌────────────────────────────────────────────────────────────────────┐
│                      HAProxyController                              │
│                   extends AbstractController                        │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - clients: Dict[str, HAProxyClient]                              │
├────────────────────────────────────────────────────────────────────┤
│ Публичные методы:                                                   │
│   + get_name() -> str  ("haproxy")                                 │
│   + handle_get(path_parts, query_params) -> Dict                   │
│   + handle_action(action_path, body) -> Dict                       │
│   + get_instances() -> List[str]                                   │
├────────────────────────────────────────────────────────────────────┤
│ Приватные методы:                                                   │
│   - _initialize_clients()                                           │
│   - _add_client(name, socket_path)                                 │
│   - _get_client(instance_name) -> HAProxyClient                    │
│   - _success_response(data, message, status_code) -> Dict          │
│   - _error_response(error, status_code) -> Dict                    │
└────────────────────────────────────────────────────────────────────┘
```

### Инициализация клиентов

**Конфигурация через `HAPROXY_INSTANCES`:**

```
Формат 1: Единичный адрес (создаст 'default' инстанс)
  "ipv4@192.168.1.1:7777"
  "/var/run/haproxy.sock"

Формат 2: Множественные с именами
  "prod=ipv4@192.168.1.1:7777,test=ipv4@192.168.1.2:7777"
  "prod=/var/run/haproxy1.sock,test=/var/run/haproxy2.sock"
```

**Алгоритм инициализации:**

```
_initialize_clients()
│
├─► Чтение HAPROXY_INSTANCES
│
├─► Если строка содержит '=':
│     │
│     └─► Парсинг: "name1=socket1,name2=socket2"
│           │
│           └─► _add_client(name, socket_path) для каждого
│
├─► Иначе (единичный адрес):
│     │
│     └─► _add_client('default', instances_config)
│
└─► Иначе (пустая конфигурация):
      │
      └─► _add_client('default', HAPROXY_SOCKET_PATH)
```

### API Endpoints

#### GET /api/v1/haproxy/instances

Список всех доступных HAProxy инстансов.

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instances": [
      {
        "name": "prod",
        "socket_path": "ipv4@192.168.1.1:7777",
        "available": true
      },
      {
        "name": "test",
        "socket_path": "ipv4@192.168.1.2:7777",
        "available": false
      }
    ],
    "count": 2
  }
}
```

#### GET /api/v1/haproxy/backends

Список бэкендов (default инстанс).

**Ответ:**
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

#### GET /api/v1/haproxy/{instance}/backends

Список бэкендов указанного инстанса.

**Пример:** `GET /api/v1/haproxy/prod/backends`

#### GET /api/v1/haproxy/backends/{backend}/servers

Серверы в бэкенде.

**Пример:** `GET /api/v1/haproxy/backends/bn_app1/servers`

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
        "addr": "192.168.1.10:8080"
      },
      {
        "name": "srv02_app1",
        "status": "DRAIN",
        "weight": "100",
        "check_status": "L7OK",
        "addr": "192.168.1.11:8080"
      }
    ],
    "count": 2
  }
}
```

#### POST /api/v1/haproxy/backends/{backend}/servers/{server}/action

Изменение состояния сервера.

**Body:**
```json
{
  "action": "drain"  // "ready", "drain", "maint"
}
```

**Пример:**
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_app1/servers/srv01_app1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'
```

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

#### POST /api/v1/haproxy/{instance}/backends/{backend}/servers/{server}/action

То же, но для указанного инстанса.

**Пример:**
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/prod/backends/bn_app1/servers/srv01_app1/action \
  -H "Content-Type: application/json" \
  -d '{"action": "maint"}'
```

### Диаграмма обработки handle_action

```
handle_action(action_path, body)
│
├─► Валидация body["action"]
│     │
│     └─► action in ["ready", "drain", "maint"]?
│           ├─ Нет → Error 400: "Invalid action"
│           └─ Да → продолжить
│
├─► Парсинг action_path:
│     │
│     ├─► Формат 1: ["backends", "bn_app", "servers", "srv01", "action"]
│     │     - instance_name = None (default)
│     │     - backend_name = "bn_app"
│     │     - server_name = "srv01"
│     │
│     └─► Формат 2: ["prod", "backends", "bn_app", "servers", "srv01", "action"]
│           - instance_name = "prod"
│           - backend_name = "bn_app"
│           - server_name = "srv01"
│
├─► _get_client(instance_name)
│     │
│     └─► HAProxyClient или ValueError
│
├─► client.set_server_state(backend_name, server_name, action)
│     │
│     ├─► Отправка команды в HAProxy socket
│     │
│     └─► True/False или исключение
│
└─► Формирование ответа
```

### Состояния серверов HAProxy

| Состояние | Описание | Поведение |
|-----------|----------|-----------|
| `ready` | Сервер активен | Принимает новые соединения |
| `drain` | Сервер в режиме drain | Завершает текущие, не принимает новые |
| `maint` | Сервер в maintenance | Не принимает соединения, помечен как недоступный |

---

## EurekaController

**Файл:** `controllers/eureka_controller.py`

### Назначение

Управление приложениями через Eureka и Spring Boot Actuator endpoints.

### Диаграмма класса

```
┌────────────────────────────────────────────────────────────────────┐
│                       EurekaController                              │
│                   extends AbstractController                        │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - client: Optional[EurekaClient]                                 │
├────────────────────────────────────────────────────────────────────┤
│ Публичные методы:                                                   │
│   + get_name() -> str  ("eureka")                                  │
│   + handle_get(path_parts, query_params) -> Dict                   │
│   + handle_action(action_path, body) -> Dict                       │
├────────────────────────────────────────────────────────────────────┤
│ Приватные методы:                                                   │
│   - _initialize_client()                                            │
│   - _get_all_apps() -> Dict                                         │
│   - _get_app_by_instance_id(instance_id) -> Dict                   │
│   - _get_app_health(instance_id) -> Dict                           │
│   - _pause_app(instance_id) -> Dict                                 │
│   - _shutdown_app(instance_id) -> Dict                             │
│   - _set_app_loglevel(instance_id, logger, level) -> Dict          │
└────────────────────────────────────────────────────────────────────┘
```

### API Endpoints

#### GET /api/v1/eureka/apps

Список всех приложений в Eureka.

**Ответ:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "total": 15,
    "applications": [
      {
        "app_name": "MY-SERVICE",
        "instance_id": "192.168.1.100:my-service:8080",
        "ip": "192.168.1.100",
        "port": 8080,
        "status": "UP",
        "home_page_url": "http://192.168.1.100:8080/",
        "health_check_url": "http://192.168.1.100:8080/actuator/health"
      }
    ]
  }
}
```

#### GET /api/v1/eureka/apps/{instance_id}

Информация о конкретном приложении.

**Пример:** `GET /api/v1/eureka/apps/192.168.1.100:my-service:8080`

#### GET /api/v1/eureka/apps/{instance_id}/health

Health check приложения через `/actuator/health`.

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
        "components": {
          "db": {"status": "UP"},
          "diskSpace": {"status": "UP"}
        }
      }
    }
  }
}
```

#### POST /api/v1/eureka/apps/{instance_id}/pause

Pause приложения через `/actuator/pause`.

**Пример:**
```bash
curl -X POST http://localhost:11011/api/v1/eureka/apps/192.168.1.100:my-service:8080/pause
```

#### POST /api/v1/eureka/apps/{instance_id}/shutdown

Graceful shutdown через `/actuator/shutdown`.

**Пример:**
```bash
curl -X POST http://localhost:11011/api/v1/eureka/apps/192.168.1.100:my-service:8080/shutdown
```

**Ответ:**
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

#### POST /api/v1/eureka/apps/{instance_id}/loglevel

Изменение уровня логирования через `/actuator/loggers`.

**Body:**
```json
{
  "logger": "com.example.myapp",  // или "ROOT"
  "level": "DEBUG"                // TRACE, DEBUG, INFO, WARN, ERROR, OFF
}
```

**Пример:**
```bash
curl -X POST http://localhost:11011/api/v1/eureka/apps/192.168.1.100:my-service:8080/loglevel \
  -H "Content-Type: application/json" \
  -d '{"logger": "ROOT", "level": "DEBUG"}'
```

### Диаграмма взаимодействия с приложениями

```
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│   FAgent          │      │     Eureka        │      │  Target App       │
│   (EurekaCtrl)    │      │     Server        │      │ (Spring Boot)     │
└────────┬──────────┘      └────────┬──────────┘      └────────┬──────────┘
         │                          │                          │
         │  1. GET /eureka/apps     │                          │
         │ ─────────────────────────►                          │
         │                          │                          │
         │  2. Applications list    │                          │
         │ ◄─────────────────────────                          │
         │                          │                          │
         │  3. Extract home_page_url│                          │
         │     from response        │                          │
         │                          │                          │
         │  4. GET /actuator/health │                          │
         │ ────────────────────────────────────────────────────►
         │                          │                          │
         │  5. Health status        │                          │
         │ ◄────────────────────────────────────────────────────
         │                          │                          │
         │  6. POST /actuator/      │                          │
         │     shutdown             │                          │
         │ ────────────────────────────────────────────────────►
         │                          │                          │
         │  7. {"message": "..."}   │                          │
         │ ◄────────────────────────────────────────────────────
         │                          │                          │
```

### Обработка ошибок

**Eureka отключен:**
```json
{
  "success": false,
  "status_code": 503,
  "error": "Eureka client is not initialized. Check EUREKA_DISCOVERY_ENABLED setting."
}
```

**Приложение не найдено:**
```json
{
  "success": false,
  "status_code": 404,
  "error": "Application with instance_id '...' not found in Eureka"
}
```

**Нет home_page_url:**
```json
{
  "success": false,
  "status_code": 400,
  "error": "Application '...' does not have home_page_url"
}
```

---

## Сравнение контроллеров

| Аспект | HAProxyController | EurekaController |
|--------|-------------------|------------------|
| Протокол связи | Unix/TCP Socket | HTTP REST API |
| Множественные инстансы | Да | Нет (один Eureka) |
| Типичные операции | drain, ready, maint | health, shutdown, pause, loglevel |
| Целевая система | HAProxy LB | Spring Boot Apps |
| Состояние | Stateless | Stateless |
