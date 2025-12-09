# Основные модули FAgent

## Содержание

1. [main.py - Точка входа](#mainpy---точка-входа)
2. [server.py - HTTP сервер](#serverpy---http-сервер)
3. [config.py - Конфигурация](#configpy---конфигурация)
4. [models.py - Модели данных](#modelspy---модели-данных)

---

## main.py - Точка входа

**Файл:** `main.py`

### Назначение

Главный модуль агента. Отвечает за:
- Инициализацию системы логирования
- Настройку обработчиков сигналов для graceful shutdown
- Создание и запуск DiscoveryManager
- Запуск HTTP сервера

### Диаграмма классов

```
main.py (функции модуля)
├── setup_logging()
├── initialize_discovery_manager()
├── setup_signal_handlers()
├── update_data_periodically()  # не используется активно
└── main()
```

### Функции

#### `setup_logging() -> None`

Настраивает систему логирования Python.

```python
def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format=Config.LOG_FORMAT
    )
```

**Поведение:**
- Читает уровень логирования из `Config.LOG_LEVEL`
- Устанавливает формат из `Config.LOG_FORMAT`

---

#### `initialize_discovery_manager() -> Optional[DiscoveryManager]`

Создает и инициализирует менеджер обнаружения.

```python
def initialize_discovery_manager() -> Optional[DiscoveryManager]:
    manager = DiscoveryManager()
    if not manager.discoverers:
        return None
    # Пробный запуск обнаружения
    apps = manager.run_discovery()
    return manager
```

**Поведение:**
1. Создает экземпляр `DiscoveryManager`
2. Проверяет, что хотя бы один плагин загружен
3. Выполняет пробное обнаружение
4. Возвращает менеджер или `None` при ошибке

**Возвращает:** `DiscoveryManager` или `None`

---

#### `setup_signal_handlers() -> None`

Настраивает обработчики системных сигналов.

```python
def setup_signal_handlers() -> None:
    def signal_handler(*_):
        # Остановка HTTP сервера в отдельном потоке
        if httpd_instance:
            shutdown_thread = threading.Thread(target=httpd_instance.shutdown)
            shutdown_thread.start()
            shutdown_thread.join(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
```

**Обрабатываемые сигналы:**
- `SIGTERM` - штатное завершение от системы
- `KeyboardInterrupt` (Ctrl+C) - обрабатывается в `main()` через try/except

**Важно:** Для корректного shutdown HTTP сервера `httpd.shutdown()` вызывается из отдельного потока, так как основной поток заблокирован в `serve_forever()`.

---

#### `main() -> int`

Главная функция запуска агента.

**Последовательность выполнения:**

```
main()
│
├─1─► setup_logging()
│
├─2─► setup_signal_handlers()
│
├─3─► initialize_discovery_manager()
│       │
│       └─► Если None → return 1
│
├─4─► run_server(discovery_manager)
│       │
│       └─► Возвращает HTTPServer instance
│
└─5─► httpd.serve_forever()
        │
        └─► Блокирующий вызов до shutdown
```

**Обработка исключений:**
- `KeyboardInterrupt` - graceful shutdown, return 0
- `OSError(errno=98)` - порт занят, логирование ошибки
- Прочие исключения - логирование, return 1

---

## server.py - HTTP сервер

**Файл:** `server.py`

### Назначение

HTTP сервер на базе стандартной библиотеки Python. Маршрутизирует входящие запросы к соответствующим обработчикам.

### Диаграмма классов

```
server.py
├── get_hostname() -> str
├── get_ip_address() -> str
├── run_server(discovery_manager, control_manager) -> HTTPServer
│
└── AgentRequestHandler(BaseHTTPRequestHandler)
        │
        ├── Атрибуты класса:
        │   ├── discovery_manager: DiscoveryManager
        │   └── control_manager: ControlManager
        │
        ├── Приватные методы:
        │   ├── _set_headers(status_code)
        │   ├── _send_error_response(code, message)
        │   ├── _get_url_path_parts() -> List[str]
        │   ├── _format_docker_apps(apps) -> List[Dict]
        │   └── _format_svc_apps(apps) -> List[Dict]
        │
        └── HTTP методы:
            ├── do_GET()
            ├── do_POST()
            └── log_message()  # переопределен, отключает стандартный лог
```

### Класс AgentRequestHandler

Наследуется от `BaseHTTPRequestHandler`. Обрабатывает HTTP запросы.

#### Атрибуты класса

```python
class AgentRequestHandler(BaseHTTPRequestHandler):
    discovery_manager: DiscoveryManager = None
    control_manager: ControlManager = None
```

Зависимости внедряются через атрибуты класса перед запуском сервера.

#### Метод do_GET()

Обрабатывает GET запросы.

**Маршруты:**

| Путь | Описание |
|------|----------|
| `/ping` | Health check, возвращает `{"status": "ok"}` |
| `/app` | Список всех обнаруженных приложений |
| `/api/v1/apps` | Alias для `/app` |
| `/api/v1/{controller}/...` | Делегирует контроллеру |

**Диаграмма обработки /app:**

```
GET /app
│
├─► discovery_manager.run_discovery()
│     │
│     └─► List[ApplicationInfo]
│
├─► Группировка приложений по source:
│     ├── docker → docker_apps
│     ├── svc    → svc_apps
│     └── eureka → (пропускается, только для обогащения)
│
├─► Форматирование:
│     ├── _format_docker_apps(docker_apps)
│     └── _format_svc_apps(svc_apps)
│
└─► JSON Response:
      {
        "server": {
          "name": "hostname",
          "ip": "192.168.1.1",
          "docker-app": { ... },  // если есть
          "site-app": { ... }
        }
      }
```

**Диаграмма обработки /api/v1/{controller}/...:**

```
GET /api/v1/haproxy/backends
│
├─► Парсинг пути: ["api", "v1", "haproxy", "backends"]
│
├─► controller_name = "haproxy"
│
├─► control_manager.get_controller("haproxy")
│     │
│     └─► HAProxyController или None
│
├─► Проверка hasattr(controller, 'handle_get')
│
├─► controller.handle_get(
│     path_parts=["backends"],
│     query_params={}
│   )
│
└─► JSON Response
```

#### Метод do_POST()

Обрабатывает POST запросы.

**Маршруты:**

| Путь | Описание |
|------|----------|
| `/api/v1/{controller}/...` | Делегирует контроллеру |
| `/api/v1/control/{controller}/...` | Старый формат (совместимость) |

**Диаграмма обработки:**

```
POST /api/v1/haproxy/backends/bn_app/servers/srv01/action
Body: {"action": "drain"}
│
├─► Парсинг пути: ["api", "v1", "haproxy", ...]
│
├─► controller_name = "haproxy"
│
├─► Чтение и парсинг JSON body
│
├─► control_manager.get_controller("haproxy")
│
├─► controller.handle_action(
│     action_path=["backends", "bn_app", "servers", "srv01", "action"],
│     body={"action": "drain"}
│   )
│
└─► JSON Response
```

### Функция run_server()

```python
def run_server(discovery_manager: DiscoveryManager,
               control_manager: ControlManager = None) -> HTTPServer:
```

**Параметры:**
- `discovery_manager` - обязательный, менеджер обнаружения
- `control_manager` - опциональный, если не передан - создается новый

**Поведение:**
1. Внедряет менеджеры в `AgentRequestHandler`
2. Если `control_manager` не передан - создает новый `ControlManager()`
3. Создает `HTTPServer` на адресе из конфига
4. Возвращает экземпляр сервера (не запускает!)

---

## config.py - Конфигурация

**Файл:** `config.py`

### Назначение

Центральное хранилище конфигурации. Все параметры читаются из переменных окружения с дефолтными значениями.

### Класс Config

```python
class Config:
    # Сервер
    SERVER_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
    SERVER_PORT = int(os.getenv("AGENT_PORT", 11011))

    # Логирование
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Discovery
    DISCOVERY_INTERVAL_SECONDS = int(os.getenv("DISCOVERY_INTERVAL", 60))
    PLUGINS_DIR = Path(__file__).parent / "plugins"

    # SVC Discovery
    SVC_APP_ROOT = Path(os.getenv("SVC_APP_ROOT", "/site/app"))
    SVC_HTPDOC_ROOT = Path(os.getenv("SVC_HTPDOC_ROOT", "/site/share/htdoc"))
    SUPPORTED_ARTIFACT_EXTENSIONS = os.getenv("SUPPORTED_ARTIFACT_EXTENSIONS", "jar,war").split(',')

    # HAProxy
    HAPROXY_SOCKET_PATH = os.getenv("HAPROXY_SOCKET_PATH", "/var/run/haproxy.sock")
    HAPROXY_INSTANCES = os.getenv("HAPROXY_INSTANCES", 'ipv4@192.168.1.1:7777')
    HAPROXY_TIMEOUT = float(os.getenv("HAPROXY_TIMEOUT", "5.0"))

    # Docker
    DOCKER_DISCOVERY_ENABLED = os.getenv("DOCKER_DISCOVERY_ENABLED", "true").lower() == "true"
    DOCKER_SOCKET_PATH = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
    DOCKER_REQUEST_TIMEOUT = int(os.getenv("DOCKER_REQUEST_TIMEOUT", "10"))

    # Eureka
    EUREKA_DISCOVERY_ENABLED = os.getenv("EUREKA_DISCOVERY_ENABLED", "false").lower() == "true"
    EUREKA_HOST = os.getenv("EUREKA_HOST", "fdse.f.ftc.ru")
    EUREKA_PORT = int(os.getenv("EUREKA_PORT", "8761"))
    EUREKA_REQUEST_TIMEOUT = int(os.getenv("EUREKA_REQUEST_TIMEOUT", "10"))

    # Безопасность (не используется активно)
    SECURITY_ENABLED = os.getenv("AGENT_SECURITY_ENABLED", "false").lower() == "true"
    AUTH_TOKEN = os.getenv("AGENT_AUTH_TOKEN", "default-please-change-me")
```

### Таблица конфигурации

| Переменная | Тип | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `AGENT_HOST` | str | `0.0.0.0` | Адрес привязки HTTP сервера |
| `AGENT_PORT` | int | `11011` | Порт HTTP сервера |
| `LOG_LEVEL` | str | `INFO` | Уровень логирования |
| `SVC_APP_ROOT` | Path | `/site/app` | Корневая директория SVC приложений |
| `SVC_HTPDOC_ROOT` | Path | `/site/share/htdoc` | Директория дистрибутивов |
| `HAPROXY_INSTANCES` | str | - | Конфигурация HAProxy инстансов |
| `HAPROXY_TIMEOUT` | float | `5.0` | Таймаут операций HAProxy |
| `DOCKER_DISCOVERY_ENABLED` | bool | `true` | Включить Docker discovery |
| `EUREKA_DISCOVERY_ENABLED` | bool | `false` | Включить Eureka discovery |

---

## models.py - Модели данных

**Файл:** `models.py`

### Назначение

Определяет структуры данных, используемые в системе.

### Класс ApplicationInfo

```python
@dataclass
class ApplicationInfo:
    name: str                              # Имя приложения
    version: str                           # Версия
    status: str                            # Статус (online, offline, maintenance)
    start_time: str = "Unknown"            # Время запуска
    metadata: Dict[str, Any] = field(default_factory=dict)  # Дополнительные данные

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует объект в словарь."""
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "start_time": self.start_time,
            **self.metadata
        }
```

### Использование metadata

Поле `metadata` содержит специфичные для источника данные:

**SVC приложения:**
```python
metadata = {
    "source": "svc",
    "pid": 12345,
    "port": 8080,
    "log_path": "/site/app/myapp/logs",
    "distr_path": "/site/share/htdoc/myapp-1.0.0.war",
    "artifact_size_bytes": 52428800,
    "artifact_size_mb": 50.0,
    "artifact_type": "war",
    "app_path": "/site/app/myapp"
}
```

**Docker контейнеры:**
```python
metadata = {
    "source": "docker",
    "container_id": "abc123...",
    "container_name": "my-app",
    "image": "registry/app",
    "tag": "v1.0.0",
    "ip": "192.168.1.100",
    "port": 8080,
    "pid": 12345,
    "compose_project_dir": "/opt/docker/my-app",
    "docker_status": "running",
    # Eureka обогащение (если включено):
    "eureka_registered": true,
    "eureka_instance_id": "192.168.1.100:my-app:8080",
    "eureka_app_name": "MY-APP",
    "eureka_status": "UP"
}
```

**Eureka приложения:**
```python
metadata = {
    "source": "eureka",
    "instance_id": "192.168.1.100:my-app:8080",
    "ip": "192.168.1.100",
    "port": 8080,
    "home_page_url": "http://192.168.1.100:8080/",
    "eureka_status": "UP",
    "vip_address": "my-app",
    "health_check_url": "http://192.168.1.100:8080/actuator/health"
}
```

### Диаграмма связей

```
ApplicationInfo
│
├── Создается в:
│   ├── SVCAppDiscoverer.discover()
│   ├── DockerDiscoverer.discover()
│   └── EurekaDiscoverer.discover()
│
├── Агрегируется в:
│   └── DiscoveryManager.run_discovery() -> List[ApplicationInfo]
│
├── Форматируется в:
│   ├── AgentRequestHandler._format_docker_apps()
│   └── AgentRequestHandler._format_svc_apps()
│
└── Сериализуется в JSON:
    └── AgentRequestHandler.do_GET() для /app
```
