# Анализ архитектуры сканирования приложений FAgent

**Дата анализа:** 2025-12-09
**Версия:** 1.0
**Автор:** Backend Architecture Review

---

## Обзор текущей архитектуры

```
┌─────────────────────────────────────────────────────────────────┐
│                        HTTP Request                              │
│                    GET /app или /api/v1/apps                     │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AgentRequestHandler                          │
│                        (server.py)                               │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DiscoveryManager                              │
│                     (discovery.py)                               │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Docker    │  │    SVC      │  │   Eureka    │              │
│  │  Discoverer │  │  Discoverer │  │  Discoverer │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
   ┌────────────┐   ┌────────────┐   ┌────────────┐
   │   Docker   │   │    svcs    │   │   Eureka   │
   │   API      │   │  subprocess│   │   HTTP     │
   └────────────┘   └────────────┘   └────────────┘
```

---

## КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### 1. Отсутствие кеширования — сканирование на каждый запрос

**Файл:** `server.py:124`, `server.py:179`

```python
# GET /app
apps = self.discovery_manager.run_discovery()  # Каждый раз!

# GET /api/v1/apps/{app_name}
apps = self.discovery_manager.run_discovery()  # Снова полное сканирование!
```

**Проблема:**
- Каждый HTTP запрос запускает **полное сканирование** всех источников
- Docker API + Eureka HTTP + subprocess вызовы svcs — всё синхронно
- При 10 запросах/сек система может деградировать
- Запрос одного приложения (`/api/v1/apps/{name}`) сканирует ВСЕ приложения

**Риск:** `КРИТИЧЕСКИЙ` — DoS при нагрузке, latency >1-5 сек

**Решение:**
```python
class DiscoveryManager:
    def __init__(self):
        self._cache: List[ApplicationInfo] = []
        self._cache_time: float = 0
        self._cache_ttl: float = 30.0  # секунды
        self._lock = threading.RLock()

    def run_discovery(self, force: bool = False) -> List[ApplicationInfo]:
        with self._lock:
            now = time.time()
            if not force and self._cache and (now - self._cache_time) < self._cache_ttl:
                return self._cache

            # Реальное сканирование
            apps = self._do_discovery()
            self._cache = apps
            self._cache_time = now
            return apps
```

---

### 2. Синхронное выполнение плагинов — блокировка потока

**Файл:** `discovery.py:57-65`

```python
def run_discovery(self) -> List[ApplicationInfo]:
    all_apps = []
    for discoverer in self.discoverers:  # Последовательно!
        try:
            apps = discoverer.discover()  # Блокирующий вызов
            all_apps.extend(apps)
        except Exception as e:
            logger.info(f"Error running discoverer...")
    return all_apps
```

**Проблема:**
- Плагины выполняются **последовательно**
- Docker (100ms) + SVC (500ms) + Eureka (200ms) = 800ms минимум
- HTTP сервер однопоточный — один медленный запрос блокирует все

**Риск:** `ВЫСОКИЙ` — низкая пропускная способность

**Решение:**
```python
import concurrent.futures

def run_discovery(self) -> List[ApplicationInfo]:
    all_apps = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.discoverers)) as executor:
        futures = {
            executor.submit(d.discover): d for d in self.discoverers
        }

        for future in concurrent.futures.as_completed(futures, timeout=30):
            try:
                apps = future.result()
                all_apps.extend(apps)
            except Exception as e:
                logger.error(f"Discoverer failed: {e}")

    return all_apps
```

---

### 3. N+1 проблема в Docker Discoverer

**Файл:** `docker_discoverer.py:244-278`

```python
containers = self.client.get_containers()  # 1 запрос - список

for container in containers:
    # Для КАЖДОГО контейнера:
    pid = self.client.get_container_pid(container_id)       # +1 API call
    compose_dir = self.client.get_container_compose_dir(container_id)  # +1 API call
    start_time = self.client.get_container_start_time(container_id)    # +1 API call
```

**Проблема:**
- При 50 контейнерах: 1 + 50×3 = **151 вызов Docker API**
- Каждый вызов `get_container_*` делает `client.containers.get(id)` — отдельный запрос

**Риск:** `ВЫСОКИЙ` — экспоненциальный рост latency

**Решение:** Использовать `_container_obj` который уже есть в данных:

```python
for container in containers:
    container_obj = container.get('_container_obj')  # Уже загружен!

    if container_obj:
        # Используем attrs напрямую — 0 дополнительных запросов
        pid = container_obj.attrs['State'].get('Pid')
        start_time = container_obj.attrs['State'].get('StartedAt')
        labels = container_obj.labels
        compose_dir = labels.get('com.docker.compose.project.config_files')
```

---

### 4. Eureka обогащение — O(n×m) сложность

**Файл:** `docker_discoverer.py:304-310`

```python
for container in containers:
    if self.eureka_client and port:
        eureka_data = self._enrich_with_eureka(server_ip, port)
```

**Файл:** `eureka_client.py:368-393`

```python
def find_app_by_ip_port(self, ip: str, port: int) -> Optional[Dict]:
    apps = self.get_applications()  # HTTP запрос на КАЖДЫЙ контейнер!

    for app in apps:
        if app_ip == ip and app_port == port:
            return app
```

**Проблема:**
- Для каждого Docker контейнера вызывается `get_applications()` — HTTP к Eureka
- При 50 контейнерах = **50 HTTP запросов к Eureka**
- Линейный поиск O(n) внутри каждого запроса

**Риск:** `КРИТИЧЕСКИЙ` — Eureka может заблокировать или rate-limit

**Решение:**
```python
class DockerDiscoverer:
    def discover(self):
        # 1 запрос к Eureka вместо N
        eureka_apps = {}
        if self.eureka_client:
            for app in self.eureka_client.get_applications():
                key = f"{app.get('ip')}:{app.get('port')}"
                eureka_apps[key] = app

        for container in containers:
            # O(1) lookup
            key = f"{server_ip}:{port}"
            eureka_data = eureka_apps.get(key, {})
```

---

## ВЫСОКИЕ РИСКИ

### 5. Subprocess без ограничений в SVC Discoverer

**Файл:** `svc_app_discoverer.py:107-131`

```python
result = subprocess.run(
    ["svcs", "-Ho", "state,stime", app_name],
    capture_output=True,
    text=True,
    timeout=10
)
```

**Проблема:**
- При 100 приложениях = **300+ subprocess вызовов** (svcs state + svcs pid + netstat)
- Каждый subprocess создаёт новый процесс ОС
- Нет пула или batching

**Риск:** `ВЫСОКИЙ` — fork bomb потенциал

**Решение:**
```python
# Batch запрос всех сервисов одной командой
result = subprocess.run(
    ["svcs", "-Ho", "fmri,state,stime", "-a"],
    capture_output=True,
    timeout=30
)
# Парсим один раз для всех приложений
```

---

### 6. Отсутствие таймаутов на уровне discovery

**Файл:** `discovery.py:62`

```python
apps = discoverer.discover()  # Без общего таймаута!
```

**Проблема:**
- Если Eureka или Docker зависнут — весь запрос зависнет
- Нет circuit breaker паттерна
- Нет fallback на частичные данные

**Риск:** `ВЫСОКИЙ` — каскадные отказы

**Решение:**
```python
def run_discovery(self) -> List[ApplicationInfo]:
    all_apps = []

    for discoverer in self.discoverers:
        try:
            with timeout(seconds=15):  # Общий таймаут на плагин
                apps = discoverer.discover()
                all_apps.extend(apps)
        except TimeoutError:
            logger.warning(f"{type(discoverer).__name__} timed out, skipping")
            continue
```

---

### 7. Однопоточный HTTP сервер

**Файл:** `server.py:349`

```python
httpd = HTTPServer(server_address, AgentRequestHandler)
```

**Проблема:**
- `HTTPServer` — однопоточный
- Один медленный запрос блокирует все остальные
- При discovery 500ms — максимум 2 RPS

**Риск:** `СРЕДНИЙ` — низкая масштабируемость

**Решение:**
```python
from http.server import ThreadingHTTPServer

httpd = ThreadingHTTPServer(server_address, AgentRequestHandler)
# или
from socketserver import ThreadingMixIn

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
```

---

## СРЕДНИЕ РИСКИ

### 8. Утечка ресурсов в Docker клиенте

**Файл:** `docker_client.py:37`

```python
self.client = docker.from_env(timeout=self.timeout)
```

**Проблема:**
- Клиент создаётся один раз, но нет явного закрытия
- При переинициализации плагина могут накапливаться соединения

**Решение:** Добавить context manager или явный close:
```python
def __del__(self):
    if self.client:
        self.client.close()
```

---

### 9. Нет валидации входных данных

**Файл:** `server.py:178`

```python
app_name = parts[3]  # Прямое использование без валидации
```

**Проблема:**
- Path traversal потенциал (хотя в данном контексте низкий)
- Возможны инъекции при логировании

**Решение:**
```python
import re

def _validate_app_name(name: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))
```

---

### 10. Хардкод временной зоны

**Файл:** `server.py:127`

```python
last_update = (datetime.now() + timedelta(hours=7)).strftime("%Y%m%d_%H%M%S")
```

**Проблема:**
- Магическое число `7` часов
- При деплое в другую зону — неправильное время

**Решение:**
```python
from datetime import timezone
import os

TZ_OFFSET = int(os.getenv("TZ_OFFSET_HOURS", "0"))
last_update = datetime.now(timezone.utc).strftime(...)
```

---

## Предлагаемая архитектура с кешированием

```
┌─────────────────────────────────────────────────────────────────┐
│                        HTTP Requests                             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ThreadedHTTPServer                              │
│                   (многопоточный)                                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CachedDiscoveryManager                        │
│         ┌────────────────────────────────────┐                   │
│         │          In-Memory Cache           │                   │
│         │      TTL=30s, Thread-safe          │                   │
│         └────────────────────────────────────┘                   │
│                          │                                       │
│                          ▼  (cache miss)                         │
│         ┌────────────────────────────────────┐                   │
│         │    Parallel Plugin Executor        │                   │
│         │    ThreadPoolExecutor(workers=3)   │                   │
│         └────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │   Docker    │     │    SVC      │     │   Eureka    │
   │  (batched)  │     │  (batched)  │     │  (cached)   │
   └─────────────┘     └─────────────┘     └─────────────┘
```

---

## Сводная таблица рисков

| # | Проблема | Severity | Файл | Effort |
|---|----------|----------|------|--------|
| 1 | Нет кеширования | КРИТИЧЕСКИЙ | discovery.py | Medium |
| 2 | Синхронные плагины | ВЫСОКИЙ | discovery.py | Low |
| 3 | N+1 Docker API | ВЫСОКИЙ | docker_discoverer.py | Low |
| 4 | N×M Eureka запросов | КРИТИЧЕСКИЙ | docker_discoverer.py | Medium |
| 5 | Subprocess flood | ВЫСОКИЙ | svc_app_discoverer.py | Medium |
| 6 | Нет таймаутов discovery | ВЫСОКИЙ | discovery.py | Low |
| 7 | Однопоточный сервер | СРЕДНИЙ | server.py | Low |
| 8 | Утечка Docker client | СРЕДНИЙ | docker_client.py | Low |
| 9 | Нет валидации input | СРЕДНИЙ | server.py | Low |
| 10 | Хардкод timezone | НИЗКИЙ | server.py | Low |

---

## Приоритеты исправлений

### Phase 1 — Quick Wins (1-2 дня)

**Цель:** Устранить самые критичные проблемы с минимальными изменениями

1. **Исправить N+1 в Docker** — использовать `_container_obj`
   - Файл: `docker_discoverer.py`
   - Ожидаемый эффект: -60% latency Docker discovery

2. **Кешировать Eureka apps в DockerDiscoverer**
   - Файл: `docker_discoverer.py`
   - Ожидаемый эффект: 1 HTTP запрос вместо N

3. **Добавить `ThreadingHTTPServer`**
   - Файл: `server.py`
   - Ожидаемый эффект: параллельная обработка запросов

### Phase 2 — Core Fixes (3-5 дней)

**Цель:** Внедрить кеширование и параллелизм

4. **Внедрить кеширование в DiscoveryManager**
   - Файл: `discovery.py`
   - TTL: 30 секунд (конфигурируемо)
   - Thread-safe реализация

5. **Параллельное выполнение плагинов**
   - Файл: `discovery.py`
   - ThreadPoolExecutor с таймаутами

6. **Добавить таймауты на discovery**
   - Файл: `discovery.py`
   - Общий таймаут + per-plugin таймаут

### Phase 3 — Optimization (1 неделя)

**Цель:** Глубокая оптимизация и мониторинг

7. **Batch запросы svcs**
   - Файл: `svc_app_discoverer.py`
   - Один вызов `svcs -a` вместо N вызовов

8. **Фоновое обновление кеша**
   - Файл: `main.py`, `discovery.py`
   - Отдельный поток для refresh

9. **Метрики и мониторинг**
   - Discovery latency
   - Cache hit/miss ratio
   - Per-plugin timing

---

## Метрики для мониторинга

После внедрения исправлений рекомендуется отслеживать:

```python
# Пример структуры метрик
metrics = {
    "discovery_total_ms": 0,           # Общее время discovery
    "discovery_cache_hits": 0,          # Попадания в кеш
    "discovery_cache_misses": 0,        # Промахи кеша
    "docker_discovery_ms": 0,           # Время Docker плагина
    "svc_discovery_ms": 0,              # Время SVC плагина
    "eureka_discovery_ms": 0,           # Время Eureka плагина
    "http_requests_total": 0,           # Всего HTTP запросов
    "http_requests_concurrent": 0,      # Параллельных запросов
}
```

---

## Заключение

Текущая архитектура имеет существенные проблемы с производительностью и масштабируемостью. Основные риски связаны с:

1. **Отсутствием кеширования** — каждый запрос выполняет полное сканирование
2. **N+1 проблемами** — избыточные запросы к Docker и Eureka API
3. **Синхронной обработкой** — блокировка потока при медленных источниках

Внедрение предложенных исправлений позволит:
- Снизить latency с 500-2000ms до 50-100ms (для кешированных ответов)
- Увеличить пропускную способность с 2 RPS до 50+ RPS
- Обеспечить устойчивость к отказам отдельных источников данных
