# FAgent - Application Discovery and Control Agent

## Описание

FAgent - это агент для обнаружения и управления приложениями на Solaris системах с интеграцией HAProxy для управления балансировкой нагрузки.

## Основные возможности

- 🔍 **Автоматическое обнаружение приложений** через Solaris SVC (Service Management Facility)
- ⚖️ **Интеграция с HAProxy** для управления состоянием серверов (ready/drain/maint)
- 🎯 **Интеграция с Eureka** для обнаружения и управления Spring Boot приложениями
- 🌐 **REST API** для запросов статуса и управления инфраструктурой
- 📦 **Ansible плейбуки** для оркестрации rolling updates
- 🔌 **Плагинная архитектура** для расширения функциональности

## Быстрый старт

### Запуск агента

```bash
# Запуск с настройками по умолчанию
./main.py

# Или с помощью Python
python3.11 main.py
```

Агент запустит HTTP сервер на `0.0.0.0:11011` (настраивается через переменные окружения).

### Проверка работы

```bash
# Health check
curl http://localhost:11011/ping

# Получить список приложений
curl http://localhost:11011/app

# Получить список HAProxy бэкендов
curl http://localhost:11011/api/v1/haproxy/backends
```

## Документация

### HAProxy API

- 📚 [HAPROXY_API.md](HAPROXY_API.md) - Основная документация HAProxy API с описанием архитектуры
- 📖 [HAPROXY_API_REFERENCE.md](HAPROXY_API_REFERENCE.md) - Полный справочник всех методов с примерами использования и сценариями автоматизации
- 📋 [HAPROXY_API_METHODS_TABLE.md](HAPROXY_API_METHODS_TABLE.md) - Сводная таблица всех доступных методов для быстрого поиска

### Eureka API

- 🚀 [EUREKA_QUICKSTART.md](EUREKA_QUICKSTART.md) - Быстрый старт с Eureka API
- 📚 [EUREKA_CONTROL_API.md](EUREKA_CONTROL_API.md) - Полная документация Eureka Control API
- 🔌 [EUREKA_PLUGIN.md](EUREKA_PLUGIN.md) - Документация Eureka discoverer плагина
- 📖 [EUREKA_API_EXAMPLES.md](EUREKA_API_EXAMPLES.md) - Примеры работы с Eureka API
- 📋 [EUREKA_CHEATSHEET.md](EUREKA_CHEATSHEET.md) - Шпаргалка по командам
- 🔗 [DOCKER_EUREKA_INTEGRATION.md](DOCKER_EUREKA_INTEGRATION.md) - Интеграция Docker ↔ Eureka

### Проект

- 🎯 [CLAUDE.md](CLAUDE.md) - Инструкции для работы с кодовой базой в Claude Code
- 🔄 [ROLLING_UPDATE_README.md](ROLLING_UPDATE_README.md) - Документация по стратегии rolling update
- 📝 [CHANGELOG.md](CHANGELOG.md) - История изменений проекта
- 🐛 [FIX_SVCS_PID_PARSING.md](FIX_SVCS_PID_PARSING.md) - Детали исправления парсинга PID из svcs

## API Endpoints

### Основные endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/ping` | Health check агента |
| GET | `/app` | Список обнаруженных приложений |

### HAProxy API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/haproxy/backends` | Список HAProxy бэкендов |
| GET | `/api/v1/haproxy/backends/{backend}/servers` | Серверы в бэкенде |
| POST | `/api/v1/haproxy/backends/{backend}/servers/{server}/action` | Управление состоянием сервера |

Полный список HAProxy методов см. в [HAPROXY_API_METHODS_TABLE.md](HAPROXY_API_METHODS_TABLE.md)

### Eureka API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/eureka/apps` | Список всех приложений в Eureka |
| GET | `/api/v1/eureka/apps/{instance_id}` | Информация о приложении |
| GET | `/api/v1/eureka/apps/{instance_id}/health` | Health check приложения |
| POST | `/api/v1/eureka/apps/{instance_id}/pause` | Pause приложения |
| POST | `/api/v1/eureka/apps/{instance_id}/shutdown` | Graceful shutdown |
| POST | `/api/v1/eureka/apps/{instance_id}/loglevel` | Изменить log level |

Полная документация: [EUREKA_CONTROL_API.md](EUREKA_CONTROL_API.md)

## Конфигурация

Все настройки через переменные окружения:

```bash
# Настройки сервера
export AGENT_HOST="0.0.0.0"
export AGENT_PORT="11011"
export LOG_LEVEL="INFO"

# Обнаружение приложений (Solaris)
export SVC_APP_ROOT="/site/app"
export SVC_HTPDOC_ROOT="/site/share/htdoc"
export SUPPORTED_ARTIFACT_EXTENSIONS="jar,war"

# HAProxy
export HAPROXY_SOCKET_PATH="/var/run/haproxy.sock"  # или "ipv4@192.168.1.15:7777"
export HAPROXY_TIMEOUT="5.0"

# Множественные HAProxy инстансы
export HAPROXY_INSTANCES="prod=/var/run/haproxy1.sock,staging=/var/run/haproxy2.sock"

# Eureka
export EUREKA_DISCOVERY_ENABLED="true"
export EUREKA_HOST="eureka.example.com"
export EUREKA_PORT="8761"
export EUREKA_REQUEST_TIMEOUT="10"
```

Подробнее см. [config.py](config.py)

## Архитектура

### Плагины Discovery

Агент использует плагинную систему для обнаружения приложений:

```
plugins/
├── svc_app_discoverer.py     # Обнаружение через Solaris SVC
├── eureka_discoverer.py      # Обнаружение через Netflix Eureka
├── docker_discoverer.py      # Обнаружение Docker контейнеров
└── your_discoverer.py        # Ваш собственный плагин
```

### Контроллеры API

Контроллеры обрабатывают API запросы:

```
controllers/
├── haproxy_controller.py  # Управление HAProxy
├── eureka_controller.py   # Управление Eureka приложениями
└── your_controller.py     # Ваш собственный контроллер
```

## Примеры использования

### Плавное отключение сервера для обслуживания

```bash
# 1. Перевести сервер в режим drain
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'

# 2. Дождаться завершения активных соединений
sleep 30

# 3. Выполнить обслуживание
# ...

# 4. Вернуть сервер в работу
curl -X POST http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers/srv01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'
```

### Мониторинг статуса

```bash
# Получить статус всех серверов
curl -s http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers | \
  jq '.data.servers[] | {name, status}'
```

Больше примеров в [HAPROXY_API_REFERENCE.md](HAPROXY_API_REFERENCE.md#примеры-использования)

## Rolling Update с Ansible

```bash
# Тестовый запуск (dry run)
./test_rolling_update.sh

# Реальное обновление
ansible-playbook multi_server_update_orchestrator_v2.yaml \
  -e "app=myapp" \
  -e "servers=srv01,srv02" \
  -e "distr_url=http://repo/myapp.war" \
  -e "backend_name=bn_myapp" \
  -e "haproxy_server=localhost:11011"
```

Подробнее см. [ROLLING_UPDATE_README.md](ROLLING_UPDATE_README.md)

## Требования

- **OS**: Solaris 11+
- **Python**: 3.11+
- **HAProxy**: 2.x или 3.x
- **Ansible**: 2.9+ (для rolling updates)

## Структура проекта

```
FAgent/
├── main.py                  # Точка входа
├── server.py               # HTTP сервер и роутинг
├── config.py               # Конфигурация
├── models.py               # Модели данных
├── discovery.py            # Менеджер обнаружения
├── control_manager.py      # Менеджер контроллеров
├── control.py              # Базовый класс контроллера
├── plugins/                # Плагины
│   ├── svc_app_discoverer.py
│   └── haproxy_client.py
├── controllers/            # Контроллеры API
│   └── haproxy_controller.py
└── ansible/                # Ansible плейбуки
    └── multi_server_update_orchestrator_v2.yaml
```

## Разработка

### Создание нового плагина обнаружения

```python
from discovery import AbstractDiscoverer
from models import ApplicationInfo

class MyDiscoverer(AbstractDiscoverer):
    def discover(self):
        # Ваша логика обнаружения
        return [ApplicationInfo(...)]
```

### Создание нового контроллера

```python
from control import AbstractController

class MyController(AbstractController):
    def get_name(self):
        return "mycontroller"

    def handle_action(self, action_path, body):
        # Обработка POST запросов
        return {"success": True, "data": {...}}
```

## Лицензия

[Укажите вашу лицензию]

## Поддержка

[Контактная информация для поддержки]

## См. также

- [Solaris SMF Documentation](https://docs.oracle.com/cd/E23824_01/html/821-1451/index.html)
- [HAProxy Documentation](http://www.haproxy.org/#docs)
- [Ansible Documentation](https://docs.ansible.com/)