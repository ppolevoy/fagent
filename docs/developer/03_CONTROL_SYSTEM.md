# Система управления (Control System)

## Обзор

Система управления позволяет выполнять действия над инфраструктурой через REST API. Построена на паттерне Controller с автоматической загрузкой.

## Компоненты

```
Control System
│
├── control.py
│   └── AbstractController (ABC)    # Базовый класс контроллеров
│
├── control_manager.py
│   └── ControlManager              # Менеджер контроллеров
│
└── controllers/
    ├── haproxy_controller.py       # Управление HAProxy
    └── eureka_controller.py        # Управление через Eureka
```

## Диаграмма классов

```
┌─────────────────────────────────────────────────────────────────┐
│                       ControlManager                             │
├─────────────────────────────────────────────────────────────────┤
│ - controllers: Dict[str, AbstractController]                     │
├─────────────────────────────────────────────────────────────────┤
│ + __init__()                                                     │
│ - _load_controllers()                                            │
│ - _load_controller_from_file(file_path)                          │
│ + get_controller(name) -> Optional[AbstractController]           │
│ + list_controllers() -> List[str]                                │
│ + has_controller(name) -> bool                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ хранит
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   <<abstract>>                                   │
│                   AbstractController                             │
├─────────────────────────────────────────────────────────────────┤
│ + get_name() -> str                            {abstract}        │
│ + handle_action(path, body) -> Dict            {abstract}        │
│ + handle_get(path, query) -> Dict              {optional}        │
└─────────────────────────────────────────────────────────────────┘
                              △
                              │ наследуют
              ┌───────────────┴───────────────┐
              │                               │
┌─────────────────────────┐     ┌─────────────────────────┐
│   HAProxyController     │     │   EurekaController      │
├─────────────────────────┤     ├─────────────────────────┤
│ + get_name() -> "haproxy│     │ + get_name() -> "eureka"│
│ + handle_action()       │     │ + handle_action()       │
│ + handle_get()          │     │ + handle_get()          │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              │ использует                    │ использует
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│    HAProxyClient        │     │     EurekaClient        │
└─────────────────────────┘     └─────────────────────────┘
```

---

## AbstractController

**Файл:** `control.py`

Абстрактный базовый класс для всех контроллеров.

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AbstractController(ABC):
    """Абстрактный базовый класс для всех контроллеров управления."""

    @abstractmethod
    def get_name(self) -> str:
        """Возвращает уникальное имя контроллера."""
        pass

    @abstractmethod
    def handle_action(self, action_path: List[str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обрабатывает POST запросы (действия).

        Args:
            action_path: Параметры из URL после /api/v1/{controller_name}/
            body: Тело POST запроса

        Returns:
            Dict с полями: success, status_code, data/error
        """
        pass

    def handle_get(self, path_parts: List[str], query_params: Dict[str, str]) -> Dict[str, Any]:
        """
        Обрабатывает GET запросы (опциональный метод).

        По умолчанию выбрасывает NotImplementedError.
        """
        raise NotImplementedError(f"Controller {self.get_name()} does not support GET")
```

### Контракт контроллера

1. Наследоваться от `AbstractController`
2. Реализовать `get_name() -> str` - уникальный идентификатор
3. Реализовать `handle_action()` - обработка POST
4. Опционально переопределить `handle_get()` - обработка GET
5. Файл должен называться `*_controller.py`
6. Файл должен находиться в `controllers/`

### Формат ответа

**Успех:**
```python
{
    "success": True,
    "status_code": 200,
    "data": {...},
    "message": "Optional message"
}
```

**Ошибка:**
```python
{
    "success": False,
    "status_code": 400,  # или другой код ошибки
    "error": "Error description"
}
```

---

## ControlManager

**Файл:** `control_manager.py`

Менеджер загружает контроллеры и предоставляет доступ к ним.

### Методы

#### `__init__()`

```python
def __init__(self):
    self.controllers: Dict[str, AbstractController] = {}
    self._load_controllers()
```

#### `_load_controllers()`

Динамически загружает контроллеры из `controllers/`.

**Алгоритм:**

```
_load_controllers()
│
├─► controllers_dir = Path(__file__).parent / "controllers"
│
├─► Для каждого *_controller.py:
│     │
│     └─► _load_controller_from_file(file_path)
│
└─► Логирование итогов
```

#### `_load_controller_from_file(file_path)`

```
_load_controller_from_file(file_path)
│
├─► Загрузить модуль через importlib
│
├─► Найти классы extends AbstractController
│
├─► Для каждого класса:
│     │
│     ├─► Создать экземпляр
│     │
│     ├─► Получить имя: controller.get_name()
│     │
│     ├─► Проверка на дубликат имени
│     │
│     └─► self.controllers[name] = instance
│
└─► Логирование
```

#### `get_controller(name) -> Optional[AbstractController]`

```python
def get_controller(self, name: str) -> Optional[AbstractController]:
    controller = self.controllers.get(name)
    if not controller:
        logger.warning(f"Controller '{name}' not found")
    return controller
```

#### `list_controllers() -> List[str]`

```python
def list_controllers(self) -> list[str]:
    return list(self.controllers.keys())
```

#### `has_controller(name) -> bool`

```python
def has_controller(self, name: str) -> bool:
    return name in self.controllers
```

---

## Маршрутизация запросов

### GET запросы

```
GET /api/v1/{controller_name}/{path...}?{query}
│
├─► server.py: AgentRequestHandler.do_GET()
│
├─► Парсинг URL: parts = ["api", "v1", "haproxy", "backends"]
│
├─► controller_name = parts[2]  # "haproxy"
│
├─► control_manager.get_controller("haproxy")
│
├─► Проверка hasattr(controller, 'handle_get')
│
├─► path_parts = parts[3:]  # ["backends"]
│
├─► query_params = parse_qsl(url.query)
│
└─► controller.handle_get(path_parts, query_params)
```

### POST запросы

```
POST /api/v1/{controller_name}/{path...}
Body: JSON
│
├─► server.py: AgentRequestHandler.do_POST()
│
├─► Парсинг URL: parts = ["api", "v1", "haproxy", "backends", ...]
│
├─► controller_name = parts[2]  # "haproxy"
│
├─► Поддержка старого формата:
│     │
│     └─► Если parts[2] == "control": controller_name = parts[3]
│
├─► control_manager.get_controller(controller_name)
│
├─► Чтение и парсинг JSON body
│
├─► action_path = parts[3:]  # ["backends", "bn_app", ...]
│
└─► controller.handle_action(action_path, body)
```

---

## Диаграмма обработки POST запроса

```
┌────────────────────────────────────────────────────────────────────┐
│  POST /api/v1/haproxy/backends/bn_app/servers/srv01/action         │
│  Body: {"action": "drain"}                                          │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│              AgentRequestHandler.do_POST()                          │
├────────────────────────────────────────────────────────────────────┤
│  1. Парсинг URL                                                     │
│     parts = ["api", "v1", "haproxy", "backends", "bn_app",         │
│              "servers", "srv01", "action"]                          │
│                                                                     │
│  2. controller_name = "haproxy"                                     │
│     action_path = ["backends", "bn_app", "servers", "srv01",       │
│                    "action"]                                        │
│                                                                     │
│  3. Чтение body = {"action": "drain"}                              │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│              control_manager.get_controller("haproxy")              │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│              HAProxyController.handle_action()                      │
├────────────────────────────────────────────────────────────────────┤
│  1. Валидация body["action"] in ["ready", "drain", "maint"]        │
│                                                                     │
│  2. Парсинг action_path:                                           │
│     - backend_name = "bn_app"                                       │
│     - server_name = "srv01"                                         │
│                                                                     │
│  3. Определение HAProxy инстанса (default или указанный)           │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│              HAProxyClient.set_server_state()                       │
├────────────────────────────────────────────────────────────────────┤
│  command = "set server bn_app/srv01 state drain"                   │
│  _send_command(command)                                             │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│              HAProxy Admin Socket                                   │
├────────────────────────────────────────────────────────────────────┤
│  Unix: /var/run/haproxy.sock                                        │
│  TCP:  ipv4@192.168.1.1:7777                                       │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│              JSON Response                                          │
├────────────────────────────────────────────────────────────────────┤
│  {                                                                  │
│    "success": true,                                                 │
│    "status_code": 200,                                              │
│    "data": {                                                        │
│      "instance": "default",                                         │
│      "backend": "bn_app",                                           │
│      "server": "srv01",                                             │
│      "action": "drain",                                             │
│      "status": "completed"                                          │
│    },                                                               │
│    "message": "Server state successfully changed to 'drain'"       │
│  }                                                                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Создание нового контроллера

### Шаблон контроллера

```python
# controllers/my_controller.py
import logging
from typing import List, Dict, Any

from control import AbstractController

logger = logging.getLogger(__name__)


class MyController(AbstractController):
    """Контроллер для управления X."""

    def __init__(self):
        """Инициализация контроллера."""
        # Инициализация клиентов, подключений и т.д.
        logger.info("MyController инициализирован")

    def get_name(self) -> str:
        """Возвращает имя контроллера для маршрутизации."""
        return "mycontroller"  # URL: /api/v1/mycontroller/...

    def handle_action(self, action_path: List[str], body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка POST запросов.

        Пример URL: POST /api/v1/mycontroller/resource/123/action
        action_path = ["resource", "123", "action"]
        body = {"param": "value"}
        """
        try:
            # Валидация
            if not body:
                return self._error_response("Request body required", 400)

            # Парсинг path
            if len(action_path) < 1:
                return self._error_response("Resource not specified", 400)

            resource = action_path[0]

            # Бизнес-логика
            result = self._do_something(resource, body)

            return self._success_response(result)

        except Exception as e:
            logger.error(f"Error in handle_action: {e}", exc_info=True)
            return self._error_response(str(e), 500)

    def handle_get(self, path_parts: List[str], query_params: Dict[str, str]) -> Dict[str, Any]:
        """
        Обработка GET запросов.

        Пример URL: GET /api/v1/mycontroller/resources?filter=active
        path_parts = ["resources"]
        query_params = {"filter": "active"}
        """
        try:
            if not path_parts or path_parts[0] == "resources":
                return self._success_response({"items": []})

            return self._error_response("Unknown endpoint", 404)

        except Exception as e:
            logger.error(f"Error in handle_get: {e}", exc_info=True)
            return self._error_response(str(e), 500)

    # Вспомогательные методы

    def _success_response(self, data: Any, message: str = None) -> Dict[str, Any]:
        response = {
            "success": True,
            "status_code": 200,
            "data": data
        }
        if message:
            response["message"] = message
        return response

    def _error_response(self, error: str, status_code: int = 500) -> Dict[str, Any]:
        return {
            "success": False,
            "status_code": status_code,
            "error": error
        }

    def _do_something(self, resource: str, params: Dict) -> Dict:
        # Бизнес-логика
        return {"resource": resource, "status": "processed"}
```

### Чек-лист для нового контроллера

- [ ] Файл называется `*_controller.py`
- [ ] Файл находится в `controllers/`
- [ ] Класс наследуется от `AbstractController`
- [ ] Реализован `get_name()` с уникальным именем
- [ ] Реализован `handle_action()` для POST
- [ ] Опционально реализован `handle_get()` для GET
- [ ] Ответы в едином формате (`success`, `status_code`, `data/error`)
- [ ] Обработаны исключения
- [ ] Добавлено логирование

---

## Обработка ошибок

### Уровни обработки

1. **Контроллер не найден** (в server.py):
```python
if not controller:
    return {"error": f"Controller '{name}' not found"}, 404
```

2. **Метод не поддерживается** (в server.py):
```python
if not hasattr(controller, 'handle_get'):
    return {"error": f"Controller does not support GET"}, 405
```

3. **Ошибка в контроллере** (в контроллере):
```python
try:
    # логика
except ValueError as e:
    return self._error_response(str(e), 400)
except ConnectionError as e:
    return self._error_response(str(e), 503)
except Exception as e:
    return self._error_response(str(e), 500)
```

4. **Ошибка парсинга JSON** (в server.py):
```python
except json.JSONDecodeError as e:
    return {"error": f"Invalid JSON: {e}"}, 400
```
