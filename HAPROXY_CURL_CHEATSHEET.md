# HAProxy API - Шпаргалка curl команд

## Переменные для удобства

```bash
# Установите эти переменные для упрощения команд
export HOST="localhost:11011"
export BACKEND="bn_webapp"
export SERVER="srv01_app1"
export INSTANCE="prod"
```

## Базовые команды

### Проверка доступности

```bash
# Health check агента
curl http://$HOST/ping

# Список приложений
curl http://$HOST/app
```

## HAProxy API команды

### GET запросы - Получение информации

```bash
# 1. Список всех доступных HAProxy инстансов
curl http://$HOST/api/v1/haproxy/instances

# 2. Список всех бэкендов (дефолтный инстанс)
curl http://$HOST/api/v1/haproxy/backends

# 3. Список всех бэкендов (конкретный инстанс)
curl http://$HOST/api/v1/haproxy/$INSTANCE/backends

# 4. Список серверов в бэкенде (дефолтный инстанс)
curl http://$HOST/api/v1/haproxy/backends/$BACKEND/servers

# 5. Список серверов в бэкенде (конкретный инстанс)
curl http://$HOST/api/v1/haproxy/$INSTANCE/backends/$BACKEND/servers
```

### POST запросы - Управление состоянием

```bash
# 5. Включить сервер (ready) - дефолтный инстанс
curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$SERVER/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'

# 6. Плавное отключение (drain) - дефолтный инстанс
curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$SERVER/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'

# 7. Режим обслуживания (maint) - дефолтный инстанс
curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$SERVER/action \
  -H "Content-Type: application/json" \
  -d '{"action": "maint"}'

# 8. Управление в конкретном инстансе (ready)
curl -X POST http://$HOST/api/v1/haproxy/$INSTANCE/backends/$BACKEND/servers/$SERVER/action \
  -H "Content-Type: application/json" \
  -d '{"action": "ready"}'

# 9. Управление в конкретном инстансе (drain)
curl -X POST http://$HOST/api/v1/haproxy/$INSTANCE/backends/$BACKEND/servers/$SERVER/action \
  -H "Content-Type: application/json" \
  -d '{"action": "drain"}'

# 10. Управление в конкретном инстансе (maint)
curl -X POST http://$HOST/api/v1/haproxy/$INSTANCE/backends/$BACKEND/servers/$SERVER/action \
  -H "Content-Type: application/json" \
  -d '{"action": "maint"}'
```

## Команды с форматированием (jq)

### Получение конкретных данных

```bash
# Только имена инстансов
curl -s http://$HOST/api/v1/haproxy/instances | jq -r '.data.instances[].name'

# Доступные инстансы
curl -s http://$HOST/api/v1/haproxy/instances | \
  jq -r '.data.instances[] | select(.available == true) | .name'

# Детальная информация об инстансах
curl -s http://$HOST/api/v1/haproxy/instances | \
  jq -r '.data.instances[] | "\(.name): \(.socket_path) - \(if .available then "✓" else "✗" end)"'

# Только имена бэкендов
curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]'

# Только имена серверов
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | jq -r '.data.servers[].name'

# Имена и статусы серверов
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | "\(.name): \(.status)"'

# Только активные серверы
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status == "UP") | .name'

# Только неактивные серверы
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status != "UP") | "\(.name): \(.status)"'

# Статус конкретного сервера
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r ".data.servers[] | select(.name == \"$SERVER\") | .status"

# Количество активных серверов
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq '[.data.servers[] | select(.status == "UP")] | length'

# Статистика по статусам
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq '.data.servers | group_by(.status) | map({status: .[0].status, count: length})'
```

## Полезные однострочники

### Операции со всеми серверами

```bash
# Drain всех активных серверов
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status == "UP") | .name' | \
  xargs -I {} curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/{}/action \
    -H "Content-Type: application/json" -d '{"action": "drain"}'

# Включить все серверы в MAINT
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status == "MAINT") | .name' | \
  xargs -I {} curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/{}/action \
    -H "Content-Type: application/json" -d '{"action": "ready"}'

# Включить все неактивные серверы
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r '.data.servers[] | select(.status != "UP") | .name' | \
  xargs -I {} curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/{}/action \
    -H "Content-Type: application/json" -d '{"action": "ready"}'
```

### Мониторинг

```bash
# Статус всех серверов во всех бэкендах
for backend in $(curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]'); do
  echo "=== $backend ==="
  curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | \
    jq -r '.data.servers[] | "\(.name): \(.status)"'
done

# Компактная статистика по всем бэкендам
for backend in $(curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]'); do
  stats=$(curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | \
    jq -r '[.data.servers[] | .status] | group_by(.) | map("\(.[0])=\(length)") | join(", ")')
  echo "$backend: $stats"
done

# Watch режим - обновление каждые 2 секунды
watch -n 2 'curl -s http://localhost:11011/api/v1/haproxy/backends/bn_webapp/servers | \
  jq -r ".data.servers[] | \"\(.name): \(.status)\""'
```

## Проверки и тестирование

```bash
# Проверка доступности HAProxy API
curl -f -s http://$HOST/api/v1/haproxy/backends > /dev/null && echo "✓ HAProxy API is UP" || echo "✗ HAProxy API is DOWN"

# Тест с обработкой ошибок
if response=$(curl -s -w "\n%{http_code}" http://$HOST/api/v1/haproxy/backends); then
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n-1)
  if [ "$http_code" = "200" ]; then
    echo "Success: $(echo $body | jq -r '.data.count') backends found"
  else
    echo "Error $http_code: $(echo $body | jq -r '.error')"
  fi
fi

# Проверка конкретного сервера с цветным выводом
STATUS=$(curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r ".data.servers[] | select(.name == \"$SERVER\") | .status")
case $STATUS in
  UP) echo -e "\033[32m✓ $SERVER is $STATUS\033[0m" ;;
  DRAIN) echo -e "\033[33m⚠ $SERVER is $STATUS\033[0m" ;;
  MAINT|DOWN) echo -e "\033[31m✗ $SERVER is $STATUS\033[0m" ;;
  *) echo "Unknown status: $STATUS" ;;
esac
```

## Пакетные операции

```bash
# Rolling restart всех серверов по одному
for server in $(curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | jq -r '.data.servers[].name'); do
  echo "Processing $server..."
  # Drain
  curl -s -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
    -H "Content-Type: application/json" -d '{"action": "drain"}' | jq -r '.message'
  sleep 10
  # Ready
  curl -s -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/$server/action \
    -H "Content-Type: application/json" -d '{"action": "ready"}' | jq -r '.message'
  sleep 5
done

# Drain серверов по шаблону имени
PATTERN="srv0[12]"  # drain srv01 и srv02
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | \
  jq -r ".data.servers[] | select(.name | test(\"$PATTERN\")) | .name" | \
  xargs -I {} curl -X POST http://$HOST/api/v1/haproxy/backends/$BACKEND/servers/{}/action \
    -H "Content-Type: application/json" -d '{"action": "drain"}'
```

## Отладка

```bash
# Verbose вывод с заголовками
curl -v http://$HOST/api/v1/haproxy/backends

# Только заголовки ответа
curl -I http://$HOST/api/v1/haproxy/backends

# С измерением времени
curl -w "\nTime: %{time_total}s\n" http://$HOST/api/v1/haproxy/backends

# Сохранение ответа в файл
curl -o response.json http://$HOST/api/v1/haproxy/backends/$BACKEND/servers

# Pretty print JSON
curl -s http://$HOST/api/v1/haproxy/backends/$BACKEND/servers | python3 -m json.tool

# Проверка с retry
curl --retry 3 --retry-delay 2 http://$HOST/api/v1/haproxy/backends
```

## Экспорт данных

```bash
# Экспорт конфигурации в CSV
echo "Backend,Server,Status,Address" > haproxy_status.csv
for backend in $(curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]'); do
  curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | \
    jq -r ".data.servers[] | \"$backend,\(.name),\(.status),\(.addr)\"" >> haproxy_status.csv
done

# Экспорт в JSON с timestamp
{
  echo '{"timestamp": "'$(date -Iseconds)'",'
  echo '"data": ['
  first=true
  for backend in $(curl -s http://$HOST/api/v1/haproxy/backends | jq -r '.data.backends[]'); do
    [ "$first" = false ] && echo ","
    first=false
    echo -n '{"backend": "'$backend'", "servers": '
    curl -s http://$HOST/api/v1/haproxy/backends/$backend/servers | jq '.data.servers'
    echo -n '}'
  done
  echo ']}'
} > haproxy_export_$(date +%Y%m%d_%H%M%S).json
```

## Алиасы для .bashrc/.zshrc

```bash
# Добавьте в ваш .bashrc или .zshrc для быстрого доступа

# Базовые алиасы
alias hap-backends='curl -s http://localhost:11011/api/v1/haproxy/backends | jq -r ".data.backends[]"'
alias hap-servers='curl -s http://localhost:11011/api/v1/haproxy/backends/$1/servers | jq ".data.servers"'

# Функции для управления
hap-ready() {
  curl -X POST http://localhost:11011/api/v1/haproxy/backends/$1/servers/$2/action \
    -H "Content-Type: application/json" -d '{"action": "ready"}'
}

hap-drain() {
  curl -X POST http://localhost:11011/api/v1/haproxy/backends/$1/servers/$2/action \
    -H "Content-Type: application/json" -d '{"action": "drain"}'
}

hap-maint() {
  curl -X POST http://localhost:11011/api/v1/haproxy/backends/$1/servers/$2/action \
    -H "Content-Type: application/json" -d '{"action": "maint"}'
}

hap-status() {
  curl -s http://localhost:11011/api/v1/haproxy/backends/$1/servers | \
    jq -r '.data.servers[] | "\(.name): \(.status)"'
}

# Использование:
# hap-backends
# hap-status bn_webapp
# hap-drain bn_webapp srv01_app1
# hap-ready bn_webapp srv01_app1
```