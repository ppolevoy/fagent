# Плагины обнаружения (Discovery Plugins)

## Обзор

Плагины обнаружения собирают информацию о приложениях из различных источников. Каждый плагин специализируется на своем типе источника.

## SVCAppDiscoverer

**Файл:** `plugins/svc_app_discoverer.py`

### Назначение

Обнаружение Java-приложений, управляемых через Solaris SVC (Service Management Facility).

### Диаграмма класса

```
┌────────────────────────────────────────────────────────────────────┐
│                       SVCAppDiscoverer                              │
│                    extends AbstractDiscoverer                       │
├────────────────────────────────────────────────────────────────────┤
│ Константы:                                                          │
│   ARTIFACT_CHECK_ORDER = ['war', 'jar', 'dir']                     │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - app_root: Path                    # /site/app                   │
│   - htdoc_root: Path                  # /site/share/htdoc          │
│   - supported_extensions: List[str]   # ['jar', 'war']             │
│   - name_mapping: Dict[str, str]      # Маппинг имен               │
├────────────────────────────────────────────────────────────────────┤
│ Публичные методы:                                                   │
│   + discover() -> List[ApplicationInfo]                            │
├────────────────────────────────────────────────────────────────────┤
│ Приватные методы:                                                   │
│   - _validate_paths()                                               │
│   - _load_name_mapping() -> Dict[str, str]                         │
│   - _get_app_status(app_name) -> Tuple[str, str]                   │
│   - _get_app_pid(app_name) -> Optional[int]                        │
│   - _parse_tomcat_server_xml(app_name) -> Optional[int]            │
│   - _get_listening_ports_netstat() -> Dict[int, int]               │
│   - _get_app_port(app_name, pid) -> Optional[int]                  │
│   - _find_artifact(app_name) -> Tuple[Path, str]                   │
│   - _build_version_pattern() -> re.Pattern                         │
│   - _extract_version(artifact_path) -> str                         │
│   - _get_artifact_metadata(...) -> Dict[str, Any]                  │
└────────────────────────────────────────────────────────────────────┘
```

### Алгоритм обнаружения

```
discover()
│
├─► Проверка существования app_root и htdoc_root
│
├─► Получение списка директорий в app_root
│
└─► Для каждого приложения:
      │
      ├─1─► _get_app_status(name)
      │       │
      │       └─► svcs -Ho state,stime {name}
      │             │
      │             └─► (status, start_time)
      │
      ├─2─► _get_app_pid(name)
      │       │
      │       └─► svcs -p -H {name}
      │             │
      │             └─► Парсинг PID из вывода
      │
      ├─3─► _get_app_port(name, pid)
      │       │
      │       ├─► _parse_tomcat_server_xml(name)
      │       │     │
      │       │     └─► Парсинг conf/server.xml
      │       │
      │       └─► fallback: _get_listening_ports_netstat()
      │
      ├─4─► _find_artifact(name)
      │       │
      │       ├─► Проверка name_mapping
      │       │
      │       └─► Поиск в htdoc_root:
      │             ├─► {name}.war (симлинк)
      │             ├─► {name}.jar (симлинк)
      │             └─► {name}/ (директория)
      │
      ├─5─► _extract_version(artifact_path)
      │       │
      │       └─► Regex: (\d+\.\d+\.\d+)
      │
      ├─6─► _get_artifact_metadata(...)
      │       │
      │       └─► Сбор metadata:
      │             - pid, port, log_path
      │             - distr_path, artifact_size
      │             - artifact_type, app_path
      │             - source = "svc"
      │
      └─7─► ApplicationInfo(name, version, status, start_time, metadata)
```

### Парсинг статуса SVC

**Команда:** `svcs -Ho state,stime {app_name}`

**Пример вывода:**
```
online         Oct_31
```

**Парсинг:**
```python
parts = output.split(" ", 1)
state = parts[0]           # "online"
start_time = parts[1].strip()  # "Oct_31"
```

### Парсинг PID из svcs -p

**Команда:** `svcs -p -H {app_name}`

**Пример вывода:**
```
online         Oct_31   -
               Oct_31 12345 java
```

**Парсинг:**
```python
for line in lines:
    if not line[0].isspace():  # Пропуск заголовков
        continue
    parts = line.strip().split()
    for part in parts:
        try:
            pid = int(part)
            return pid
        except ValueError:
            continue
```

### Поиск порта

**Приоритет:**
1. Парсинг `conf/server.xml` (для Tomcat)
2. Fallback: `netstat -an -P tcp`

**Парсинг server.xml:**
```python
# Ищем HTTP Connector
pattern = r'<Connector[^>]*port=["\'](\d+)["\'][^>]*protocol=["\']HTTP'
match = re.search(pattern, content, re.IGNORECASE)
port = int(match.group(1))
```

### Маппинг имен приложений

**Файл:** `app_name_mapping.json`

```json
{
  "doc-print": "document-printable",
  "app1": "application-one-dist",
  "special-app": "/opt/custom/special-app-1.0.0.war"
}
```

**Поддерживаемые форматы:**
- Относительное имя: ищется в `htdoc_root`
- Абсолютный путь: используется напрямую

---

## DockerDiscoverer

**Файл:** `plugins/docker_discoverer.py`

### Назначение

Обнаружение Docker контейнеров с опциональным обогащением данными из Eureka.

### Диаграмма класса

```
┌────────────────────────────────────────────────────────────────────┐
│                       DockerDiscoverer                              │
│                    extends AbstractDiscoverer                       │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - enabled: bool                                                   │
│   - timeout: int                                                    │
│   - client: DockerClient                                            │
│   - eureka_client: Optional[EurekaClient]                          │
│   - eureka_enabled: bool                                            │
├────────────────────────────────────────────────────────────────────┤
│ Публичные методы:                                                   │
│   + discover() -> List[ApplicationInfo]                            │
├────────────────────────────────────────────────────────────────────┤
│ Приватные методы:                                                   │
│   - _get_server_ip() -> str                                         │
│   - _map_docker_status(docker_status) -> str                       │
│   - _extract_status_from_state(state) -> str                       │
│   - _enrich_with_eureka(ip, port) -> dict                          │
│   - _format_start_time(start_time) -> str                          │
└────────────────────────────────────────────────────────────────────┘
```

### Алгоритм обнаружения

```
discover()
│
├─► Проверка enabled и client
│
├─► client.get_containers(all_containers=False)
│     │
│     └─► Список запущенных контейнеров
│
├─► server_ip = _get_server_ip()
│
└─► Для каждого контейнера:
      │
      ├─► Извлечение базовой информации:
      │     - container_id, container_name
      │     - image_full, status_string, ports_string
      │
      ├─► client.parse_image_tag(image_full)
      │     │
      │     └─► (image, tag)
      │
      ├─► client.parse_port_mapping(ports_string)
      │     │
      │     └─► port (int или None)
      │
      ├─► client.get_container_pid(container_id)
      │
      ├─► client.get_container_compose_dir(container_id)
      │
      ├─► client.get_container_start_time(container_id)
      │
      ├─► _map_docker_status(_extract_status_from_state(status))
      │     │
      │     └─► "online", "offline", "maintenance", etc.
      │
      ├─► Создание metadata:
      │     │
      │     └─► source="docker", container_id, container_name,
      │         image, tag, ip, port, pid, compose_project_dir
      │
      ├─► Если eureka_enabled и port:
      │     │
      │     └─► _enrich_with_eureka(server_ip, port)
      │           │
      │           └─► Добавление eureka_* полей в metadata
      │
      └─► ApplicationInfo(name, version=tag, status, start_time, metadata)
```

### Маппинг статусов Docker

```python
status_mapping = {
    "running": "online",
    "exited": "offline",
    "paused": "maintenance",
    "restarting": "restarting",
    "created": "offline",
    "removing": "offline",
    "dead": "offline"
}
```

### Обогащение Eureka

Если `EUREKA_DISCOVERY_ENABLED=true`, для каждого контейнера:

```
_enrich_with_eureka(ip, port)
│
├─► eureka_client.find_app_by_ip_port(ip, port)
│
└─► Если найдено:
      {
        "eureka_registered": true,
        "eureka_instance_id": "192.168.1.100:my-app:8080",
        "eureka_app_name": "MY-APP",
        "eureka_status": "UP",
        "eureka_url": "http://...",
        "eureka_health_url": "http://.../actuator/health",
        "eureka_vip": "my-app"
      }
```

---

## EurekaDiscoverer

**Файл:** `plugins/eureka_discoverer.py`

### Назначение

Обнаружение приложений, зарегистрированных в Eureka Service Registry.

### Диаграмма класса

```
┌────────────────────────────────────────────────────────────────────┐
│                       EurekaDiscoverer                              │
│                    extends AbstractDiscoverer                       │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - enabled: bool                                                   │
│   - host: str                                                       │
│   - port: int                                                       │
│   - timeout: int                                                    │
│   - client: EurekaClient                                            │
├────────────────────────────────────────────────────────────────────┤
│ Публичные методы:                                                   │
│   + discover() -> List[ApplicationInfo]                            │
├────────────────────────────────────────────────────────────────────┤
│ Приватные методы:                                                   │
│   - _extract_version_from_metadata(metadata) -> str                │
│   - _map_eureka_status(eureka_status) -> str                       │
└────────────────────────────────────────────────────────────────────┘
```

### Алгоритм обнаружения

```
discover()
│
├─► Проверка enabled и client
│
├─► client.get_applications()
│     │
│     └─► GET /eureka/apps (JSON)
│
└─► Для каждого приложения:
      │
      ├─► Извлечение:
      │     - app_name, instance_id
      │     - ip_addr, port, status
      │     - home_page_url, metadata
      │
      ├─► _extract_version_from_metadata(metadata)
      │     │
      │     └─► Поиск в полях: version, app.version, build.version
      │
      ├─► _map_eureka_status(status)
      │     │
      │     └─► UP->online, DOWN->offline, etc.
      │
      └─► ApplicationInfo(
            name=app_name,
            version=version,
            status=mapped_status,
            start_time="unknown",
            metadata={
              "source": "eureka",
              "instance_id": instance_id,
              "ip": ip_addr,
              "port": port,
              "home_page_url": home_page_url,
              "eureka_status": status,
              "vip_address": vip,
              "health_check_url": health_url
            }
          )
```

### Маппинг статусов Eureka

```python
status_mapping = {
    "UP": "online",
    "DOWN": "offline",
    "STARTING": "starting",
    "OUT_OF_SERVICE": "maintenance",
    "UNKNOWN": "unknown"
}
```

**Важно:** Eureka-приложения используются в основном для обогащения Docker контейнеров. В ответе `/app` они группируются отдельно и могут быть пропущены в финальном выводе.

---

## Низкоуровневые клиенты

### DockerClient

**Файл:** `plugins/docker_client.py`

Клиент для работы с Docker через библиотеку `docker-py`.

```
┌────────────────────────────────────────────────────────────────────┐
│                         DockerClient                                │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - timeout: int                                                    │
│   - client: docker.DockerClient                                     │
├────────────────────────────────────────────────────────────────────┤
│ Методы:                                                             │
│   + get_containers(all_containers=False) -> List[Dict]             │
│   + get_container_inspect(container_id) -> Optional[Dict]          │
│   + get_container_compose_dir(container_id) -> Optional[str]       │
│   + get_container_pid(container_id) -> Optional[int]               │
│   + get_container_start_time(container_id) -> Optional[str]        │
│   + parse_port_mapping(ports_string) -> Optional[int]              │
│   + parse_image_tag(image_string) -> Tuple[str, str]               │
│   - _check_docker_available() -> bool                               │
│   - _format_ports(ports: Dict) -> str                               │
└────────────────────────────────────────────────────────────────────┘
```

**Зависимости:** `docker>=7.0.0`

### EurekaClient

**Файл:** `plugins/eureka_client.py`

Клиент для работы с Eureka REST API.

```
┌────────────────────────────────────────────────────────────────────┐
│                         EurekaClient                                │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - host: str                                                       │
│   - port: int                                                       │
│   - timeout: int                                                    │
│   - base_url: str                                                   │
├────────────────────────────────────────────────────────────────────┤
│ Методы:                                                             │
│   + get_applications() -> List[Dict]                               │
│   + find_app_by_ip_port(ip, port) -> Optional[Dict]                │
│   + check_app_health(home_page_url) -> Dict                        │
│   + shutdown_app(home_page_url) -> Dict                            │
│   + pause_app(home_page_url) -> Dict                               │
│   + set_app_loglevel(url, logger, level) -> Dict                   │
│   - _parse_instance(instance, app_name) -> Optional[Dict]          │
│   - _extract_ip_from_instance(instance) -> str                     │
│   - _extract_port(instance) -> int                                  │
│   - _is_valid_ip(ip_string) -> bool                                 │
└────────────────────────────────────────────────────────────────────┘
```

**Зависимости:** `requests`

### HAProxyClient

**Файл:** `plugins/haproxy_client.py`

Клиент для работы с HAProxy через Admin Socket.

```
┌────────────────────────────────────────────────────────────────────┐
│                         HAProxyClient                               │
├────────────────────────────────────────────────────────────────────┤
│ Константы:                                                          │
│   VALID_STATES = ['ready', 'drain', 'maint']                       │
│   DEFAULT_TIMEOUT = 5.0                                             │
├────────────────────────────────────────────────────────────────────┤
│ Атрибуты:                                                           │
│   - socket_path_str: str                                            │
│   - timeout: float                                                  │
│   - socket_type: str            # 'unix' или 'tcp4'                │
│   - address: Union[Path, Tuple] # Path или (host, port)            │
├────────────────────────────────────────────────────────────────────┤
│ Методы:                                                             │
│   + get_info() -> Dict[str, str]                                   │
│   + get_backends() -> List[str]                                    │
│   + get_backend_servers(backend_name) -> List[Dict]                │
│   + set_server_state(backend, server, state) -> bool               │
│   + get_server_state(backend, server) -> Optional[Dict]            │
│   + health_check() -> bool                                          │
│   - _parse_socket_path(socket_path) -> Tuple[str, ...]             │
│   - _validate_socket()                                              │
│   - _send_command(command) -> str                                   │
│   - _parse_csv_response(response) -> List[Dict]                    │
└────────────────────────────────────────────────────────────────────┘
```

**Поддерживаемые форматы socket:**
- Unix socket: `/var/run/haproxy.sock`
- TCP IPv4: `ipv4@192.168.1.15:7777`

**HAProxy команды:**
- `show info` - информация о HAProxy
- `show stat` - статистика (CSV)
- `set server {backend}/{server} state {state}` - изменение состояния
