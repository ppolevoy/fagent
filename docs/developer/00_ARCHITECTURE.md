# FAgent - Архитектура проекта

## Обзор

FAgent (Application Discovery and Control Agent) - агент для автоматического обнаружения и управления Java-приложениями. Разработан для работы в среде Solaris с SVC (Service Management Facility), а также поддерживает Docker контейнеры и интеграцию с Eureka.

## Структура проекта

```
FAgent/project/
├── main.py                 # Точка входа, инициализация агента
├── server.py               # HTTP сервер и маршрутизация запросов
├── config.py               # Конфигурация через переменные окружения
├── models.py               # Модели данных (ApplicationInfo)
├── discovery.py            # Система обнаружения приложений
├── control.py              # Базовый класс контроллеров
├── control_manager.py      # Менеджер контроллеров
├── plugins/                # Плагины обнаружения
│   ├── svc_app_discoverer.py    # Обнаружение SVC приложений
│   ├── docker_discoverer.py     # Обнаружение Docker контейнеров
│   ├── eureka_discoverer.py     # Обнаружение приложений в Eureka
│   ├── docker_client.py         # Клиент Docker API
│   ├── eureka_client.py         # Клиент Eureka REST API
│   └── haproxy_client.py        # Клиент HAProxy Admin Socket
├── controllers/            # Контроллеры управления
│   ├── haproxy_controller.py    # API управления HAProxy
│   └── eureka_controller.py     # API управления через Eureka
└── docs/                   # Документация
    └── developer/          # Документация для разработчиков
```

## Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FAgent                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        main.py                                    │   │
│  │  - Точка входа                                                    │   │
│  │  - Настройка логирования                                          │   │
│  │  - Обработка сигналов (SIGTERM, SIGINT)                          │   │
│  │  - Graceful shutdown                                              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                       server.py                                   │   │
│  │  ┌──────────────────────────────────────────────────────────┐    │   │
│  │  │              AgentRequestHandler                          │    │   │
│  │  │  - GET /ping           → Health check                     │    │   │
│  │  │  - GET /app            → Discovery (все приложения)       │    │   │
│  │  │  - GET /api/v1/*       → Controllers (GET)                │    │   │
│  │  │  - POST /api/v1/*      → Controllers (POST/action)        │    │   │
│  │  └──────────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│              ┌───────────────┴───────────────┐                          │
│              ▼                               ▼                          │
│  ┌───────────────────────┐      ┌───────────────────────┐              │
│  │   DiscoveryManager    │      │    ControlManager     │              │
│  │   (discovery.py)      │      │  (control_manager.py) │              │
│  └───────────────────────┘      └───────────────────────┘              │
│              │                               │                          │
│              ▼                               ▼                          │
│  ┌───────────────────────┐      ┌───────────────────────┐              │
│  │      plugins/         │      │     controllers/      │              │
│  │  *_discoverer.py      │      │    *_controller.py    │              │
│  ├───────────────────────┤      ├───────────────────────┤              │
│  │ - SVCAppDiscoverer    │      │ - HAProxyController   │              │
│  │ - DockerDiscoverer    │      │ - EurekaController    │              │
│  │ - EurekaDiscoverer    │      └───────────────────────┘              │
│  └───────────────────────┘                   │                          │
│              │                               │                          │
│              ▼                               ▼                          │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                      Клиенты (plugins/)                        │     │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │     │
│  │  │DockerClient │  │EurekaClient │  │   HAProxyClient     │   │     │
│  │  │(docker-py)  │  │(REST API)   │  │(Unix/TCP Socket)    │   │     │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Solaris SVC  │    │    Docker     │    │   HAProxy     │
│  (svcs cmd)   │    │   Daemon      │    │    Socket     │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
                     ┌───────────────┐
                     │    Eureka     │
                     │   Server      │
                     └───────────────┘
```

## Паттерны проектирования

### 1. Plugin Pattern (Плагинная архитектура)

Система обнаружения построена на плагинах. Каждый плагин:
- Наследуется от `AbstractDiscoverer`
- Реализует метод `discover() -> List[ApplicationInfo]`
- Автоматически загружается из директории `plugins/` по шаблону `*_discoverer.py`

```python
class AbstractDiscoverer(ABC):
    @abstractmethod
    def discover(self) -> List[ApplicationInfo]:
        pass
```

### 2. Controller Pattern (Паттерн контроллера)

Система управления построена на контроллерах. Каждый контроллер:
- Наследуется от `AbstractController`
- Реализует `get_name()`, `handle_action()`, опционально `handle_get()`
- Автоматически загружается из `controllers/` по шаблону `*_controller.py`

```python
class AbstractController(ABC):
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def handle_action(self, action_path: List[str], body: Dict) -> Dict:
        pass
```

### 3. Dependency Injection

Зависимости внедряются через атрибуты класса `AgentRequestHandler`:

```python
AgentRequestHandler.discovery_manager = discovery_manager
AgentRequestHandler.control_manager = control_manager
```

## Поток данных

### Запуск агента

```
main()
  │
  ├─► setup_logging()           # Настройка логирования
  │
  ├─► setup_signal_handlers()   # Обработчики SIGTERM
  │
  ├─► initialize_discovery_manager()
  │     │
  │     └─► DiscoveryManager()
  │           │
  │           └─► _load_plugins()
  │                 │
  │                 └─► Для каждого *_discoverer.py:
  │                       - Загрузить модуль
  │                       - Найти класс extends AbstractDiscoverer
  │                       - Создать экземпляр
  │
  └─► run_server()
        │
        ├─► ControlManager()
        │     │
        │     └─► _load_controllers()
        │           │
        │           └─► Для каждого *_controller.py:
        │                 - Загрузить модуль
        │                 - Найти класс extends AbstractController
        │                 - Создать экземпляр
        │
        └─► HTTPServer.serve_forever()
```

### Обработка запроса Discovery

```
GET /app
  │
  ├─► AgentRequestHandler.do_GET()
  │
  ├─► discovery_manager.run_discovery()
  │     │
  │     └─► Для каждого discoverer:
  │           │
  │           └─► discoverer.discover()
  │                 │
  │                 └─► List[ApplicationInfo]
  │
  ├─► Группировка по source (docker, svc, eureka)
  │
  └─► JSON Response
```

### Обработка Control запроса

```
POST /api/v1/haproxy/backends/bn_app/servers/srv01/action
Body: {"action": "drain"}
  │
  ├─► AgentRequestHandler.do_POST()
  │
  ├─► control_manager.get_controller("haproxy")
  │
  ├─► controller.handle_action(
  │     ["backends", "bn_app", "servers", "srv01", "action"],
  │     {"action": "drain"}
  │   )
  │     │
  │     └─► haproxy_client.set_server_state("bn_app", "srv01", "drain")
  │           │
  │           └─► Отправка команды в HAProxy socket
  │
  └─► JSON Response
```

## Конфигурация

Вся конфигурация через переменные окружения (см. `config.py`):

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `AGENT_HOST` | Хост HTTP сервера | `0.0.0.0` |
| `AGENT_PORT` | Порт HTTP сервера | `11011` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `SVC_APP_ROOT` | Корень SVC приложений | `/site/app` |
| `SVC_HTPDOC_ROOT` | Корень дистрибутивов | `/site/share/htdoc` |
| `HAPROXY_INSTANCES` | HAProxy инстансы | - |
| `DOCKER_DISCOVERY_ENABLED` | Включить Docker | `true` |
| `EUREKA_DISCOVERY_ENABLED` | Включить Eureka | `false` |

## Формат ответа API

Все API ответы следуют единому формату:

**Успех:**
```json
{
  "success": true,
  "status_code": 200,
  "data": { ... },
  "message": "Optional message"
}
```

**Ошибка:**
```json
{
  "success": false,
  "status_code": 400,
  "error": "Error description"
}
```

## Graceful Shutdown

При получении SIGTERM или SIGINT:
1. Логируется сообщение о начале остановки
2. HTTP сервер останавливается в отдельном потоке
3. Ожидание завершения потока (timeout 5 сек)
4. Выход с кодом 0
