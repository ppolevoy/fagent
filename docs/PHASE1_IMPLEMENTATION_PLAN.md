# Phase 1: Quick Wins — План реализации

**Цель:** Устранить критичные проблемы производительности с минимальными изменениями
**Срок:** 1-2 дня
**Ожидаемый эффект:** Снижение latency на 60-80%, увеличение RPS в 10+ раз

---

## Обзор задач Phase 1

| # | Задача | Файл | Сложность | Риск | Приоритет |
|---|--------|------|-----------|------|-----------|
| 1.1 | Исправить N+1 в Docker Discoverer | `docker_discoverer.py` | Низкая | Низкий | P0 |
| 1.2 | Кешировать Eureka apps | `docker_discoverer.py` | Низкая | Низкий | P0 |
| 1.3 | ThreadingHTTPServer | `server.py` | Низкая | Низкий | P1 |

---

## Задача 1.1: Исправление N+1 в Docker Discoverer

### Текущее состояние

**Файл:** `plugins/docker_discoverer.py`, строки 271-278

```python
# ПРОБЛЕМА: 3 дополнительных API вызова на КАЖДЫЙ контейнер
pid = self.client.get_container_pid(container_id)           # API call #1
compose_dir = self.client.get_container_compose_dir(container_id)  # API call #2
start_time = self.client.get_container_start_time(container_id)    # API call #3
```

**Проблема:** При 50 контейнерах = 151 вызов Docker API (1 + 50×3)

### Решение

Объект `_container_obj` уже содержит все необходимые данные — используем его напрямую.

**Файл:** `plugins/docker_client.py`, строка 80 — уже сохраняет объект:
```python
'_container_obj': container  # Объект уже загружен!
```

### План изменений

#### Шаг 1.1.1: Добавить вспомогательный метод в DockerDiscoverer

**Файл:** `plugins/docker_discoverer.py`

**Добавить метод после `_format_start_time()` (около строки 228):**

```python
def _extract_container_details(self, container: dict) -> dict:
    """
    Извлечение деталей контейнера из _container_obj (без дополнительных API вызовов).

    Args:
        container: Словарь с данными контейнера от get_containers()

    Returns:
        dict с pid, start_time, compose_dir
    """
    container_obj = container.get('_container_obj')

    if not container_obj:
        # Fallback на старый метод если объект недоступен
        container_id = container.get('ID', '')
        return {
            'pid': self.client.get_container_pid(container_id) if container_id else None,
            'start_time': self.client.get_container_start_time(container_id) if container_id else None,
            'compose_dir': self.client.get_container_compose_dir(container_id) if container_id else None
        }

    # Быстрый путь: извлекаем из уже загруженного объекта
    try:
        state = container_obj.attrs.get('State', {})
        pid = state.get('Pid')
        if pid == 0:
            pid = None

        start_time = state.get('StartedAt')
        if start_time == "0001-01-01T00:00:00Z":
            start_time = None

        # Compose директория из labels
        labels = container_obj.labels or {}
        compose_path = labels.get('com.docker.compose.project.config_files')
        compose_dir = None
        if compose_path:
            import os
            compose_dir = os.path.dirname(compose_path) if os.path.isfile(compose_path) else compose_path

        return {
            'pid': pid,
            'start_time': start_time,
            'compose_dir': compose_dir
        }

    except Exception as e:
        logger.warning(f"Ошибка извлечения деталей контейнера: {e}")
        return {'pid': None, 'start_time': None, 'compose_dir': None}
```

#### Шаг 1.1.2: Изменить метод discover()

**Файл:** `plugins/docker_discoverer.py`

**Заменить строки 271-282:**

```python
# БЫЛО:
pid = self.client.get_container_pid(container_id)
compose_dir = self.client.get_container_compose_dir(container_id)
start_time = self.client.get_container_start_time(container_id)
if start_time:
    start_time = self._format_start_time(start_time)
else:
    start_time = "Unknown"
```

**НА:**

```python
# СТАЛО: Извлекаем всё из уже загруженного объекта (0 дополнительных API вызовов)
details = self._extract_container_details(container)
pid = details['pid']
compose_dir = details['compose_dir']
start_time = details['start_time']
if start_time:
    start_time = self._format_start_time(start_time)
else:
    start_time = "Unknown"
```

### Тестирование

```bash
# 1. Запустить тест Docker discoverer
cd /site/app/FAgent/project
python3 -c "
from plugins.docker_discoverer import DockerDiscoverer
import time

d = DockerDiscoverer()

start = time.time()
apps = d.discover()
elapsed = time.time() - start

print(f'Найдено контейнеров: {len(apps)}')
print(f'Время выполнения: {elapsed*1000:.0f}ms')
"

# 2. Ожидаемый результат: время < 200ms для 50 контейнеров (было ~1500ms)
```

### Критерии успеха

- [ ] Время Docker discovery снижено на 60%+
- [ ] Все контейнеры обнаруживаются корректно
- [ ] PID, start_time, compose_dir заполняются правильно
- [ ] Нет регрессий в API ответах

---

## Задача 1.2: Кеширование Eureka Apps

### Текущее состояние

**Файл:** `plugins/docker_discoverer.py`, строки 304-310

```python
# ПРОБЛЕМА: HTTP запрос к Eureka на КАЖДЫЙ контейнер
for container in containers:
    if self.eureka_client and port:
        eureka_data = self._enrich_with_eureka(server_ip, port)  # HTTP call!
```

**Файл:** `plugins/eureka_client.py`, строка 382

```python
def find_app_by_ip_port(self, ip: str, port: int):
    apps = self.get_applications()  # HTTP запрос каждый раз!
    for app in apps:
        if app_ip == ip and app_port == port:
            return app
```

**Проблема:** При 50 контейнерах = 50 HTTP запросов к Eureka

### Решение

Загрузить все Eureka apps ОДИН раз перед циклом, использовать dict для O(1) lookup.

### План изменений

#### Шаг 1.2.1: Добавить метод предзагрузки Eureka

**Файл:** `plugins/docker_discoverer.py`

**Добавить метод после `_extract_container_details()` (или после `_enrich_with_eureka()`):**

```python
def _load_eureka_apps_map(self) -> dict:
    """
    Предзагрузка всех приложений из Eureka в словарь для быстрого поиска.

    Returns:
        dict: Словарь {ip:port -> eureka_app_data}
    """
    eureka_map = {}

    if not self.eureka_client:
        return eureka_map

    try:
        apps = self.eureka_client.get_applications()

        for app in apps:
            ip = app.get('ip', '')
            port = app.get('port', 0)

            if ip and port:
                key = f"{ip}:{port}"
                eureka_map[key] = {
                    "eureka_registered": True,
                    "eureka_instance_id": app.get("instance_id", ""),
                    "eureka_app_name": app.get("app_name", ""),
                    "eureka_status": app.get("status", "UNKNOWN"),
                    "eureka_url": app.get("home_page_url", ""),
                    "eureka_health_url": app.get("health_check_url", ""),
                    "eureka_vip": app.get("vip_address", "")
                }

        logger.debug(f"Загружено {len(eureka_map)} приложений из Eureka")

    except Exception as e:
        logger.warning(f"Ошибка загрузки приложений из Eureka: {e}")

    return eureka_map
```

#### Шаг 1.2.2: Изменить метод discover()

**Файл:** `plugins/docker_discoverer.py`

**Добавить перед циклом `for container in containers:` (около строки 250):**

```python
# Предзагружаем Eureka данные ОДИН раз (вместо запроса на каждый контейнер)
eureka_apps_map = {}
if self.eureka_client:
    eureka_apps_map = self._load_eureka_apps_map()
    logger.debug(f"Eureka: предзагружено {len(eureka_apps_map)} приложений")
```

**Заменить строки 304-310:**

```python
# БЫЛО:
if self.eureka_client and port:
    eureka_data = self._enrich_with_eureka(server_ip, port)
    if eureka_data:
        metadata.update(eureka_data)
        if eureka_data.get("eureka_registered"):
            logger.debug(f"Docker контейнер {container_name} зарегистрирован в Eureka...")
```

**НА:**

```python
# СТАЛО: O(1) lookup вместо HTTP запроса
if eureka_apps_map and port:
    eureka_key = f"{server_ip}:{port}"
    eureka_data = eureka_apps_map.get(eureka_key)
    if eureka_data:
        metadata.update(eureka_data)
        logger.debug(f"Docker контейнер {container_name} найден в Eureka: {eureka_data.get('eureka_instance_id')}")
    else:
        metadata["eureka_registered"] = False
```

### Тестирование

```bash
# 1. Проверить что Eureka данные загружаются
cd /site/app/FAgent/project
python3 -c "
from plugins.docker_discoverer import DockerDiscoverer
import time

# Включаем Eureka для теста
import config
config.Config.EUREKA_DISCOVERY_ENABLED = True

d = DockerDiscoverer()

start = time.time()
apps = d.discover()
elapsed = time.time() - start

print(f'Найдено контейнеров: {len(apps)}')
print(f'Время выполнения: {elapsed*1000:.0f}ms')

# Проверяем Eureka данные
for app in apps[:3]:
    print(f'{app.name}: eureka_registered={app.metadata.get(\"eureka_registered\")}')
"
```

### Критерии успеха

- [ ] Только 1 HTTP запрос к Eureka (вместо N)
- [ ] Eureka данные корректно сопоставляются с контейнерами
- [ ] Время discovery с Eureka снижено на 80%+

---

## Задача 1.3: ThreadingHTTPServer

### Текущее состояние

**Файл:** `server.py`, строка 349

```python
httpd = HTTPServer(server_address, AgentRequestHandler)
```

**Проблема:** Однопоточный сервер — один запрос блокирует все остальные

### Решение

Заменить `HTTPServer` на `ThreadingHTTPServer` (встроенный в Python).

### План изменений

#### Шаг 1.3.1: Изменить импорты

**Файл:** `server.py`

**Заменить строку 6:**

```python
# БЫЛО:
from http.server import BaseHTTPRequestHandler, HTTPServer
```

**НА:**

```python
# СТАЛО:
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
```

#### Шаг 1.3.2: Изменить создание сервера

**Файл:** `server.py`

**Заменить строку 349:**

```python
# БЫЛО:
httpd = HTTPServer(server_address, AgentRequestHandler)
```

**НА:**

```python
# СТАЛО: Многопоточный сервер для параллельной обработки запросов
httpd = ThreadingHTTPServer(server_address, AgentRequestHandler)
```

#### Шаг 1.3.3: Обновить логирование

**Файл:** `server.py`

**Заменить строку 350:**

```python
# БЫЛО:
logger.info(f"HTTP сервер создан на {Config.SERVER_HOST}:{Config.SERVER_PORT}")
```

**НА:**

```python
# СТАЛО:
logger.info(f"HTTP сервер (threading) создан на {Config.SERVER_HOST}:{Config.SERVER_PORT}")
```

### Тестирование

```bash
# 1. Запустить агент
./fagent.sh restart

# 2. Тест параллельных запросов с помощью curl
# Запустить в трёх терминалах одновременно:
time curl http://localhost:11011/api/v1/apps

# 3. Или использовать ab (Apache Benchmark)
ab -n 100 -c 10 http://localhost:11011/ping

# Ожидаемый результат:
# - Requests per second: >100 (было ~2)
# - Параллельные запросы не блокируют друг друга
```

### Критерии успеха

- [ ] Параллельные запросы обрабатываются одновременно
- [ ] Нет блокировки при медленном discovery
- [ ] RPS увеличен в 10+ раз

---

## Порядок внедрения

### День 1

| Время | Задача | Действия |
|-------|--------|----------|
| 1-2 часа | 1.1 Docker N+1 | Добавить `_extract_container_details()`, изменить `discover()` |
| 30 мин | Тестирование 1.1 | Проверить время discovery, корректность данных |
| 1-2 часа | 1.2 Eureka cache | Добавить `_load_eureka_apps_map()`, изменить `discover()` |
| 30 мин | Тестирование 1.2 | Проверить Eureka enrichment |

### День 2

| Время | Задача | Действия |
|-------|--------|----------|
| 30 мин | 1.3 ThreadingHTTPServer | Изменить импорт и создание сервера |
| 1 час | Интеграционное тестирование | ab, curl, проверка всех API endpoints |
| 1 час | Документация | Обновить CHANGELOG, записать метрики до/после |

---

## Чеклист перед деплоем

### Функциональные тесты

- [ ] `GET /ping` возвращает `{"status": "ok"}`
- [ ] `GET /app` возвращает список приложений
- [ ] `GET /api/v1/apps` возвращает список приложений
- [ ] `GET /api/v1/apps/{name}` возвращает конкретное приложение
- [ ] Docker контейнеры обнаруживаются с корректными PID, port, start_time
- [ ] Eureka enrichment работает (если включен)

### Тесты производительности

- [ ] Discovery latency < 500ms (для 50 контейнеров)
- [ ] Eureka enrichment добавляет < 100ms
- [ ] Параллельные запросы не блокируют друг друга
- [ ] ab тест: RPS > 50 для `/ping`

### Регрессионные тесты

- [ ] Все существующие API endpoints работают
- [ ] Формат JSON ответов не изменился
- [ ] Логирование работает корректно
- [ ] Graceful shutdown работает

---

## Метрики для сравнения

### До Phase 1

```
Docker Discovery (50 контейнеров):
  - API calls: 151 (1 + 50×3)
  - Latency: ~1500ms

Eureka Enrichment (50 контейнеров):
  - HTTP requests: 50
  - Latency: ~2500ms

HTTP Server:
  - Max RPS: ~2
  - Concurrent requests: 1
```

### После Phase 1 (ожидаемые)

```
Docker Discovery (50 контейнеров):
  - API calls: 1
  - Latency: ~200ms (-87%)

Eureka Enrichment (50 контейнеров):
  - HTTP requests: 1
  - Latency: ~300ms (-88%)

HTTP Server:
  - Max RPS: ~100+
  - Concurrent requests: unlimited (thread per request)
```

---

## Rollback план

В случае проблем — откат через git:

```bash
# Сохранить текущие изменения
git stash

# Или откатить конкретные файлы
git checkout HEAD -- plugins/docker_discoverer.py
git checkout HEAD -- server.py

# Перезапустить агент
./fagent.sh restart
```

---

## Следующие шаги (Phase 2)

После успешного внедрения Phase 1:

1. **Кеширование в DiscoveryManager** — TTL-based cache для всех плагинов
2. **Параллельное выполнение плагинов** — ThreadPoolExecutor
3. **Таймауты на уровне discovery** — защита от зависших источников
