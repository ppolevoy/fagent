# HAProxy API Документация

## Обзор

HAProxy API предоставляет возможность управления серверами HAProxy через REST API.

## Архитектура

Решение состоит из трех компонентов:

1. **HAProxy Client Plugin** ([plugins/haproxy_client.py](plugins/haproxy_client.py))
   - Низкоуровневая работа с HAProxy через Unix Socket
   - Обработка ошибок подключения
   - Парсинг ответов HAProxy

2. **HAProxy Controller** ([controllers/haproxy_controller.py](controllers/haproxy_controller.py))
   - API логика
   - Валидация запросов
   - Единый формат ответов
   - Поддержка множественных инстансов

3. **Server Integration** ([server.py](server.py))
   - Роутинг HTTP запросов
   - Интеграция с ControlManager

## Конфигурация

### Единичный инстанс HAProxy

#### Unix Socket (по умолчанию)

```bash
export HAPROXY_SOCKET_PATH="/var/run/haproxy.sock"
export HAPROXY_TIMEOUT="5.0"
```

**Конфигурация HAProxy (haproxy.cfg):**
```
global
    stats socket /var/run/haproxy.sock mode 660 level admin
```

#### TCP Socket (IPv4)

```bash
export HAPROXY_SOCKET_PATH="ipv4@192.168.1.15:7777"
export HAPROXY_TIMEOUT="5.0"
```

**Конфигурация HAProxy (haproxy.cfg):**
```
global
    stats socket ipv4@192.168.1.15:7777 level admin
```

### Множественные инстансы HAProxy

#### Единичный адрес (без имени)

Если указан только один адрес без имени, он будет использован как `default` инстанс:

```bash
# Unix socket
export HAPROXY_INSTANCES="/var/run/haproxy.sock"

# TCP IPv4
export HAPROXY_INSTANCES="ipv4@192.168.1.1:7777"

export HAPROXY_TIMEOUT="5.0"
```

#### Все Unix Sockets

```bash
# Формат: "name1=socket1,name2=socket2"
export HAPROXY_INSTANCES="prod=/var/run/haproxy1.sock,staging=/var/run/haproxy2.sock"
export HAPROXY_TIMEOUT="5.0"
```

#### Смешанная конфигурация (Unix + TCP)

```bash
# Можно комбинировать Unix и TCP sockets
export HAPROXY_INSTANCES="prod=/var/run/haproxy-prod.sock,remote=ipv4@192.168.1.15:7777,backup=ipv4@192.168.1.16:7777"
export HAPROXY_TIMEOUT="5.0"
```

#### Только TCP Sockets (IPv4)

```bash
export HAPROXY_INSTANCES="dc1=ipv4@10.0.1.10:7777,dc2=ipv4@10.0.2.10:7777"
export HAPROXY_TIMEOUT="5.0"
```

## API Эндпоинты

### 1. Получить список бэкендов

**GET** `/api/v1/haproxy/backends`

**Пример запроса:**
```bash
curl http://localhost:11011/api/v1/haproxy/backends
```

**Пример ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backends": ["myapp", "api", "static"],
    "count": 3
  }
}
```

### 2. Получить серверы в бэкенде

**GET** `/api/v1/haproxy/backends/{backend_name}/servers`

**Пример запроса:**
```bash
curl http://localhost:11011/api/v1/haproxy/backends/myapp/servers
```

**Пример ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "data": {
    "instance": "default",
    "backend": "myapp",
    "servers": [
      {
        "name": "web01",
        "status": "UP",
        "weight": "1",
        "check_status": "L4OK",
        "check_duration": "0",
        "last_chg": "12345",
        "downtime": "0",
        "addr": "192.168.1.10:8080",
        "cookie": ""
      },
      {
        "name": "web02",
        "status": "MAINT",
        "weight": "1",
        "check_status": "L4OK",
        "check_duration": "0",
        "last_chg": "123",
        "downtime": "0",
        "addr": "192.168.1.11:8080",
        "cookie": ""
      }
    ],
    "count": 2
  }
}
```

### 3. Изменить состояние сервера

**POST** `/api/v1/haproxy/backends/{backend_name}/servers/{server_name}/action`

**Body:**
```json
{
  "action": "drain|ready|maint"
}
```

**Допустимые действия:**
- `ready` - Включить сервер (готов принимать трафик)
- `drain` - Graceful shutdown (не принимает новые подключения, завершает текущие)
- `maint` - Режим обслуживания (сервер недоступен)

**Пример запроса (drain):**
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/myapp/servers/web01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'
```

**Пример ответа:**
```json
{
  "success": true,
  "status_code": 200,
  "message": "Состояние сервера успешно изменено на 'drain'",
  "data": {
    "instance": "default",
    "backend": "myapp",
    "server": "web01",
    "action": "drain",
    "status": "completed"
  }
}
```

**Пример запроса (ready):**
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/myapp/servers/web01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'
```

## Работа с множественными инстансами

При настройке множественных инстансов HAProxy, можно указывать имя инстанса в URL:

### Получить бэкенды конкретного инстанса

**GET** `/api/v1/haproxy/{instance_name}/backends`

```bash
curl http://localhost:11011/api/v1/haproxy/prod/backends
```

### Получить серверы конкретного инстанса

**GET** `/api/v1/haproxy/{instance_name}/backends/{backend_name}/servers`

```bash
curl http://localhost:11011/api/v1/haproxy/prod/backends/myapp/servers
```

### Изменить состояние сервера в конкретном инстансе

**POST** `/api/v1/haproxy/{instance_name}/backends/{backend_name}/servers/{server_name}/action`

```bash
curl -X POST http://localhost:11011/api/v1/haproxy/prod/backends/myapp/servers/web01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'
```

## Формат ответов

### Успешный ответ

```json
{
  "success": true,
  "status_code": 200,
  "data": { ... },
  "message": "Optional success message"
}
```

### Ответ с ошибкой

```json
{
  "success": false,
  "status_code": 400|404|500|503,
  "error": "Error message"
}
```

## HTTP коды ответов

- `200` - Успешно
- `400` - Некорректный запрос (невалидные параметры)
- `404` - Ресурс не найден (контроллер, бэкенд, сервер)
- `500` - Внутренняя ошибка сервера
- `502` - Ошибка выполнения команды HAProxy
- `503` - HAProxy недоступен

## Поддерживаемые типы подключений

HAProxy Client Plugin поддерживает три типа подключений:

### 1. Unix Domain Socket
- **Формат**: `/var/run/haproxy.sock` (обычный путь к файлу)
- **Использование**: Локальное подключение на том же сервере
- **Производительность**: Максимальная (без сетевого стека)
- **Безопасность**: Контролируется правами доступа к файлу
- **HAProxy Config**: `stats socket /var/run/haproxy.sock mode 660 level admin`

### 2. TCP Socket IPv4
- **Формат**: `ipv4@192.168.1.15:7777`
- **Использование**: Удаленное подключение или привязка к конкретному IP
- **Производительность**: Хорошая (небольшой overhead TCP)
- **Безопасность**: Требует защиты firewall и/или SSL
- **HAProxy Config**: `stats socket ipv4@192.168.1.15:7777 level admin`

**Примечание**: Unix и TCP сокеты можно комбинировать в конфигурации множественных инстансов.

## Логирование

Все операции логируются с указанием:
- Типа операции (GET/POST)
- Типа подключения (unix/tcp4)
- Параметров запроса
- Результата выполнения
- Ошибок с полным stack trace

Уровни логирования:
- `INFO` - успешные операции
- `WARNING` - валидационные ошибки
- `ERROR` - ошибки подключения и выполнения

## Примеры использования

### Типичный workflow: Graceful restart сервера

1. **Перевести сервер в drain режим:**
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/myapp/servers/web01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'
```

2. **Дождаться завершения текущих соединений (мониторинг вне API)**

3. **Выполнить обслуживание сервера**

4. **Вернуть сервер в работу:**
```bash
curl -X POST http://localhost:11011/api/v1/haproxy/backends/myapp/servers/web01/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'
```

### Проверка статуса всех серверов

```bash
# Получить список бэкендов
curl http://localhost:11011/api/v1/haproxy/backends | jq '.data.backends[]'

# Для каждого бэкенда получить серверы
for backend in $(curl -s http://localhost:11011/api/v1/haproxy/backends | jq -r '.data.backends[]'); do
  echo "Backend: $backend"
  curl -s http://localhost:11011/api/v1/haproxy/backends/$backend/servers | jq '.data.servers[] | {name, status}'
done
```

## Безопасность

### Unix Socket

1. **Права доступа**: Убедитесь, что процесс агента имеет права на чтение/запись HAProxy socket
   ```bash
   # Проверить права
   ls -la /var/run/haproxy.sock

   # Установить правильные права (если нужно)
   chmod 660 /var/run/haproxy.sock
   chown haproxy:haproxy /var/run/haproxy.sock
   ```

2. **Рекомендация**: Используйте Unix socket для локального взаимодействия - это наиболее безопасный вариант

### TCP Socket

1. **Firewall**: ОБЯЗАТЕЛЬНО настройте firewall для ограничения доступа к TCP порту
   ```bash
   # Разрешить только с конкретного IP агента
   iptables -A INPUT -p tcp --dport 7777 -s 192.168.1.100 -j ACCEPT
   iptables -A INPUT -p tcp --dport 7777 -j DROP

   # Или через firewalld
   firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.100" port port="7777" protocol="tcp" accept'
   firewall-cmd --reload
   ```

2. **Bind Address**: Привязывайте к конкретному IP, а не к 0.0.0.0
   ```
   # ✅ Хорошо - слушаем только внутренний интерфейс
   stats socket ipv4@192.168.1.15:7777 level admin

   # ❌ Плохо - слушаем на всех интерфейсах (включая публичные)
   stats socket ipv4@0.0.0.0:7777 level admin
   ```

3. **Сетевая сегментация**: Используйте TCP socket только в доверенных сетях (management VLAN)

4. **SSL/TLS**: HAProxy Runtime API не поддерживает нативно SSL. Используйте:
   - VPN туннель (OpenVPN, WireGuard)
   - SSH туннель: `ssh -L 7777:localhost:7777 haproxy-server`
   - Stunnel для SSL обертки

5. **Мониторинг**: Включите логирование всех подключений к порту
   ```bash
   # Мониторинг подключений
   watch 'netstat -tnp | grep :7777'
   ```

### Общие рекомендации

1. **Аутентификация агента**: Рекомендуется использовать `AGENT_SECURITY_ENABLED=true` и `AGENT_AUTH_TOKEN`
   ```bash
   export AGENT_SECURITY_ENABLED=true
   export AGENT_AUTH_TOKEN="secure-random-token-here"
   ```

2. **Аудит**: Все операции логируются для отслеживания изменений
   - Логи агента: содержат все API запросы и HAProxy команды
   - Логи HAProxy: можно включить логирование Runtime API команд

3. **Least Privilege**: HAProxy socket должен иметь минимально необходимый уровень доступа
   ```
   # Если нужен только мониторинг (без изменений)
   stats socket /var/run/haproxy.sock mode 660 level operator

   # Для полного управления (drain, maint, ready)
   stats socket /var/run/haproxy.sock mode 660 level admin
   ```

4. **Ротация токенов**: Регулярно меняйте `AGENT_AUTH_TOKEN` если используется аутентификация

## Устранение неполадок

### HAProxy socket не найден

```json
{
  "success": false,
  "status_code": 503,
  "error": "Ошибка подключения к HAProxy: Socket file not found: /var/run/haproxy.sock"
}
```

**Решение:**
- Проверьте путь к socket: `ls -la /var/run/haproxy.sock`
- Проверьте права доступа
- Убедитесь, что HAProxy запущен

### Таймаут подключения

```json
{
  "success": false,
  "status_code": 503,
  "error": "Ошибка подключения к HAProxy: Таймаут при выполнении команды"
}
```

**Решение:**
- Увеличьте `HAPROXY_TIMEOUT`
- Проверьте, что HAProxy не перегружен
- Проверьте логи HAProxy

### Сервер не найден

```json
{
  "success": false,
  "status_code": 502,
  "error": "Ошибка HAProxy: No such server"
}
```

**Решение:**
- Проверьте правильность имени бэкенда и сервера
- Используйте GET запрос для получения актуального списка серверов

### TCP подключение отклонено (Connection refused)

```json
{
  "success": false,
  "status_code": 503,
  "error": "Ошибка подключения к HAProxy: [Errno 111] Connection refused"
}
```

**Решение:**
- Убедитесь, что HAProxy запущен: `systemctl status haproxy`
- Проверьте, что в haproxy.cfg настроен TCP socket:
  ```
  stats socket ipv4@192.168.1.15:7777 level admin
  ```
- Проверьте, что порт слушается: `netstat -tlnp | grep 7777`
- Проверьте firewall: `iptables -L | grep 7777` или `firewall-cmd --list-ports`

### Неверный формат socket_path

```json
{
  "success": false,
  "status_code": 503,
  "error": "Ошибка подключения к HAProxy: Invalid IPv4 format: ipv4@192.168.1.15. Expected: ipv4@host:port"
}
```

**Решение:**
- IPv4 формат: `ipv4@192.168.1.15:7777` (обязателен порт)
- Unix формат: `/var/run/haproxy.sock` (без префикса)

### Невалидный порт

```json
{
  "success": false,
  "status_code": 503,
  "error": "Invalid port: 99999"
}
```

**Решение:**
- Порт должен быть в диапазоне 1-65535
- Проверьте HAPROXY_SOCKET_PATH или HAPROXY_INSTANCES

### Таймаут при TCP подключении

```json
{
  "success": false,
  "status_code": 503,
  "error": "Ошибка подключения к HAProxy: [Errno 110] Connection timed out"
}
```

**Решение:**
- Увеличьте `HAPROXY_TIMEOUT` (по умолчанию 5.0 секунд)
- Проверьте сетевую доступность: `telnet 192.168.1.15 7777`
- Проверьте маршрутизацию: `ping 192.168.1.15`

## Версии HAProxy

Плагин протестирован с HAProxy версий 2.x и 3.x.

Используемые команды HAProxy:
- `show info` - информация о HAProxy
- `show stat` - статистика серверов
- `set server <backend>/<server> state <state>` - изменение состояния сервера
