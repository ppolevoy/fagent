# Система обнаружения приложений (Discovery System)

## Обзор

Система обнаружения построена на плагинной архитектуре. Она автоматически загружает и запускает плагины для сбора информации о приложениях из различных источников.

## Компоненты

```
Discovery System
│
├── discovery.py
│   ├── AbstractDiscoverer (ABC)  # Базовый класс плагинов
│   └── DiscoveryManager          # Менеджер плагинов
│
└── plugins/
    ├── svc_app_discoverer.py     # Solaris SVC приложения
    ├── docker_discoverer.py      # Docker контейнеры
    └── eureka_discoverer.py      # Eureka регистрация
```

## Диаграмма классов

```
┌─────────────────────────────────────────────────────────────────┐
│                      DiscoveryManager                            │
├─────────────────────────────────────────────────────────────────┤
│ - discoverers: List[AbstractDiscoverer]                         │
├─────────────────────────────────────────────────────────────────┤
│ + __init__()                                                     │
│ - _load_plugins()                                                │
│ + run_discovery() -> List[ApplicationInfo]                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ создает и хранит
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   <<abstract>>                                   │
│                   AbstractDiscoverer                             │
├─────────────────────────────────────────────────────────────────┤
│ + discover() -> List[ApplicationInfo]  {abstract}               │
└─────────────────────────────────────────────────────────────────┘
                              △
                              │ наследуют
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ SVCAppDiscoverer│  │DockerDiscoverer │  │EurekaDiscoverer │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ + discover()    │  │ + discover()    │  │ + discover()    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
          │                   │                   │
          │ использует        │ использует        │ использует
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   svcs (CLI)    │  │  DockerClient   │  │  EurekaClient   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## AbstractDiscoverer

**Файл:** `discovery.py`

Абстрактный базовый класс для всех плагинов обнаружения.

```python
from abc import ABC, abstractmethod
from typing import List
from models import ApplicationInfo

class AbstractDiscoverer(ABC):
    """Абстрактный базовый класс для всех плагинов обнаружения."""

    @abstractmethod
    def discover(self) -> List[ApplicationInfo]:
        """
        Основной метод, который должен быть реализован в каждом плагине.
        Должен возвращать список обнаруженных приложений.
        """
        pass
```

### Контракт плагина

1. Наследоваться от `AbstractDiscoverer`
2. Реализовать метод `discover() -> List[ApplicationInfo]`
3. Файл должен называться `*_discoverer.py`
4. Файл должен находиться в директории `plugins/`

---

## DiscoveryManager

**Файл:** `discovery.py`

Менеджер загружает плагины и координирует процесс обнаружения.

### Методы

#### `__init__()`

```python
def __init__(self):
    self.discoverers: List[AbstractDiscoverer] = []
    self._load_plugins()
```

Создает пустой список плагинов и вызывает загрузку.

#### `_load_plugins()`

Динамически загружает все плагины из директории `plugins/`.

**Алгоритм:**

```
_load_plugins()
│
├─► Получить путь: Config.PLUGINS_DIR
│
├─► Для каждого файла *_discoverer.py:
│     │
│     ├─► Загрузить модуль через importlib
│     │
│     ├─► Найти все классы в модуле
│     │
│     ├─► Для каждого класса:
│     │     │
│     │     ├─► Проверка: issubclass(cls, AbstractDiscoverer)
│     │     │
│     │     ├─► Проверка: cls is not AbstractDiscoverer
│     │     │
│     │     └─► Создать экземпляр и добавить в self.discoverers
│     │
│     └─► Логирование ошибок при импорте/инициализации
│
└─► Логирование итогов
```

**Код:**

```python
def _load_plugins(self):
    for file_path in Config.PLUGINS_DIR.glob("*_discoverer.py"):
        module_name = file_path.stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        issubclass(obj, AbstractDiscoverer) and
                        obj is not AbstractDiscoverer):
                        try:
                            instance = obj()
                            self.discoverers.append(instance)
                        except Exception as e:
                            logger.warning(f"Failed to initialize {name}: {e}")
        except ImportError as e:
            logger.warning(f"Failed to import {module_name}: {e}")
```

#### `run_discovery() -> List[ApplicationInfo]`

Запускает обнаружение на всех загруженных плагинах.

```python
def run_discovery(self) -> List[ApplicationInfo]:
    all_apps = []
    for discoverer in self.discoverers:
        try:
            apps = discoverer.discover()
            all_apps.extend(apps)
        except Exception as e:
            logger.info(f"Error running {type(discoverer).__name__}: {e}")
    return all_apps
```

**Поведение:**
- Вызывает `discover()` на каждом плагине
- Объединяет результаты в один список
- Ошибки отдельных плагинов не прерывают общий процесс

---

## Диаграмма процесса обнаружения

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GET /app request                                 │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   DiscoveryManager.run_discovery()                      │
└────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ SVCAppDiscoverer │       │ DockerDiscoverer │       │ EurekaDiscoverer │
│   .discover()    │       │    .discover()   │       │   .discover()    │
└──────────────────┘       └──────────────────┘       └──────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    svcs -Ho      │       │ docker.containers│       │  GET /eureka/    │
│    state,stime   │       │     .list()      │       │     apps         │
└──────────────────┘       └──────────────────┘       └──────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│List[Application  │       │List[Application  │       │List[Application  │
│     Info]        │       │     Info]        │       │     Info]        │
│ source="svc"     │       │ source="docker"  │       │ source="eureka"  │
└──────────────────┘       └──────────────────┘       └──────────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │  Объединенный список  │
                        │ List[ApplicationInfo] │
                        └──────────────────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │  Группировка по      │
                        │  metadata["source"]  │
                        └──────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │  docker   │   │    svc    │   │  eureka   │
            │   apps    │   │   apps    │   │(пропуск)  │
            └───────────┘   └───────────┘   └───────────┘
                    │               │
                    ▼               ▼
            ┌───────────────────────────────┐
            │         JSON Response         │
            │  {                            │
            │    "server": {                │
            │      "docker-app": {...},     │
            │      "site-app": {...}        │
            │    }                          │
            │  }                            │
            └───────────────────────────────┘
```

---

## Создание нового плагина

### Шаблон плагина

```python
# plugins/my_discoverer.py
import logging
from typing import List

from discovery import AbstractDiscoverer
from models import ApplicationInfo

logger = logging.getLogger(__name__)


class MyDiscoverer(AbstractDiscoverer):
    """Плагин для обнаружения приложений из источника X."""

    def __init__(self):
        """Инициализация плагина."""
        super().__init__()
        # Инициализация клиентов, проверка доступности и т.д.
        logger.info("MyDiscoverer инициализирован")

    def discover(self) -> List[ApplicationInfo]:
        """
        Обнаружение приложений.

        Returns:
            List[ApplicationInfo]: Список обнаруженных приложений
        """
        apps = []

        try:
            # Логика обнаружения
            # ...

            app = ApplicationInfo(
                name="my-app",
                version="1.0.0",
                status="online",
                start_time="2025-01-01T00:00:00Z",
                metadata={
                    "source": "my-source",  # Важно указать source!
                    "custom_field": "value"
                }
            )
            apps.append(app)

        except Exception as e:
            logger.error(f"Ошибка в MyDiscoverer: {e}")

        return apps
```

### Чек-лист для нового плагина

- [ ] Файл называется `*_discoverer.py`
- [ ] Файл находится в `plugins/`
- [ ] Класс наследуется от `AbstractDiscoverer`
- [ ] Реализован метод `discover() -> List[ApplicationInfo]`
- [ ] В `metadata` указан `source` для идентификации
- [ ] Обработаны исключения (плагин не должен ломать других)
- [ ] Добавлено логирование

---

## Порядок загрузки плагинов

Плагины загружаются в алфавитном порядке имен файлов:

1. `docker_discoverer.py`
2. `eureka_discoverer.py`
3. `svc_app_discoverer.py`

Порядок влияет на порядок в результирующем списке, но не на функциональность.

---

## Обработка ошибок

### На уровне загрузки плагина

```
Ошибка импорта модуля → WARNING в лог → Плагин пропущен
Ошибка инициализации класса → WARNING в лог → Плагин пропущен
```

### На уровне выполнения discover()

```
Исключение в discover() → INFO в лог → Продолжение с другими плагинами
```

Это обеспечивает устойчивость системы: сбой одного плагина не влияет на работу остальных.
