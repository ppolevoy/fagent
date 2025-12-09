# FAgent - Документация для разработчика

## Содержание

Документация разбита на модули для удобства навигации:

| Файл | Описание |
|------|----------|
| [00_ARCHITECTURE.md](00_ARCHITECTURE.md) | Общая архитектура проекта, паттерны проектирования, потоки данных |
| [01_CORE_MODULES.md](01_CORE_MODULES.md) | Основные модули: main.py, server.py, config.py, models.py |
| [02_DISCOVERY_SYSTEM.md](02_DISCOVERY_SYSTEM.md) | Система обнаружения приложений: AbstractDiscoverer, DiscoveryManager |
| [03_CONTROL_SYSTEM.md](03_CONTROL_SYSTEM.md) | Система управления: AbstractController, ControlManager |
| [04_PLUGINS.md](04_PLUGINS.md) | Плагины обнаружения: SVC, Docker, Eureka и их клиенты |
| [05_CONTROLLERS.md](05_CONTROLLERS.md) | Контроллеры: HAProxyController, EurekaController |
| [06_API_REFERENCE.md](06_API_REFERENCE.md) | Справочник REST API с примерами |
| [07_DIAGRAMS.md](07_DIAGRAMS.md) | Диаграммы процессов и взаимодействий |
| [08_SCANNING_PROCESS.md](08_SCANNING_PROCESS.md) | **Детальный процесс сканирования и сбора данных** |

## Быстрый старт для разработчика

### 1. Структура проекта

```
FAgent/project/
├── main.py                 # Точка входа
├── server.py               # HTTP сервер
├── config.py               # Конфигурация
├── models.py               # Модели данных
├── discovery.py            # Система обнаружения
├── control.py              # Базовый класс контроллеров
├── control_manager.py      # Менеджер контроллеров
├── plugins/                # Плагины обнаружения
│   ├── svc_app_discoverer.py
│   ├── docker_discoverer.py
│   ├── eureka_discoverer.py
│   ├── docker_client.py
│   ├── eureka_client.py
│   └── haproxy_client.py
└── controllers/            # Контроллеры управления
    ├── haproxy_controller.py
    └── eureka_controller.py
```

### 2. Ключевые концепции

#### Плагинная архитектура

**Discovery плагины** автоматически загружаются из `plugins/*_discoverer.py`:

```python
from discovery import AbstractDiscoverer
from models import ApplicationInfo

class MyDiscoverer(AbstractDiscoverer):
    def discover(self) -> List[ApplicationInfo]:
        # Логика обнаружения
        return apps
```

**Контроллеры** автоматически загружаются из `controllers/*_controller.py`:

```python
from control import AbstractController

class MyController(AbstractController):
    def get_name(self) -> str:
        return "mycontroller"

    def handle_action(self, action_path, body) -> Dict:
        # Обработка POST
        return {"success": True, "status_code": 200, "data": {...}}

    def handle_get(self, path_parts, query_params) -> Dict:
        # Обработка GET (опционально)
        return {"success": True, "status_code": 200, "data": {...}}
```

### 3. Основные API endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/ping` | Health check |
| GET | `/app` | Список всех приложений |
| GET | `/api/v1/haproxy/backends` | Бэкенды HAProxy |
| POST | `/api/v1/haproxy/backends/{bn}/servers/{srv}/action` | Управление сервером |
| GET | `/api/v1/eureka/apps` | Приложения в Eureka |
| POST | `/api/v1/eureka/apps/{id}/shutdown` | Shutdown приложения |

### 4. Конфигурация

Через переменные окружения:

```bash
export AGENT_PORT=11011
export LOG_LEVEL=DEBUG
export HAPROXY_INSTANCES="prod=ipv4@192.168.1.1:7777"
export DOCKER_DISCOVERY_ENABLED=true
export EUREKA_DISCOVERY_ENABLED=false
```

### 5. Запуск

```bash
python3.11 main.py
```

### 6. Тестирование API

```bash
# Health check
curl http://localhost:11011/ping

# Список приложений
curl http://localhost:11011/app

# HAProxy серверы
curl http://localhost:11011/api/v1/haproxy/backends/bn_app/servers

# Drain сервер
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_app/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'
```

## Рекомендуемый порядок изучения

1. **[00_ARCHITECTURE.md](00_ARCHITECTURE.md)** - начните с общего понимания архитектуры
2. **[01_CORE_MODULES.md](01_CORE_MODULES.md)** - изучите основные модули
3. **[02_DISCOVERY_SYSTEM.md](02_DISCOVERY_SYSTEM.md)** - поймите как работает обнаружение
4. **[08_SCANNING_PROCESS.md](08_SCANNING_PROCESS.md)** - детально изучите процесс сканирования
5. **[03_CONTROL_SYSTEM.md](03_CONTROL_SYSTEM.md)** - поймите как работает управление
6. **[04_PLUGINS.md](04_PLUGINS.md)** - изучите конкретные плагины
7. **[05_CONTROLLERS.md](05_CONTROLLERS.md)** - изучите контроллеры
8. **[06_API_REFERENCE.md](06_API_REFERENCE.md)** - используйте как справочник
9. **[07_DIAGRAMS.md](07_DIAGRAMS.md)** - визуальное понимание процессов

## Дополнительная документация

Смотрите также файлы в корне проекта:
- `CLAUDE.md` - инструкции для AI-ассистентов
- `CHANGELOG.md` - история изменений
- `HAPROXY_API.md` - детальная документация HAProxy API
- `ROLLING_UPDATE_README.md` - документация по rolling update

## Контакты

При возникновении вопросов обращайтесь к команде разработки.
