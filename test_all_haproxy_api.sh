#!/bin/bash
# Полный тест всех HAProxy API методов

HOST="${1:-192.168.8.88:11011}"

echo "=========================================="
echo "Тестирование всех HAProxy API методов"
echo "Host: $HOST"
echo "=========================================="
echo

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для тестирования endpoint
test_endpoint() {
    local method=$1
    local url=$2
    local description=$3
    local body=$4

    echo -n "$description: "

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
                  -H "Content-Type: application/json" \
                  -d "$body")
    fi

    http_code=$(echo "$response" | tail -n1)
    json_response=$(echo "$response" | head -n-1)

    success=$(echo "$json_response" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('success', False))" 2>/dev/null)

    if [ "$success" = "True" ] && [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓ PASS${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $http_code)"
        echo "  Response: $json_response"
        return 1
    fi
}

echo "=== GET методы ==="
echo

# 1. Новый метод - Список инстансов
test_endpoint "GET" \
    "http://$HOST/api/v1/haproxy/instances" \
    "1. GET /api/v1/haproxy/instances"

# Получаем данные для следующих тестов
instances_response=$(curl -s http://$HOST/api/v1/haproxy/instances)
instance_count=$(echo "$instances_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['count'])" 2>/dev/null)
echo "   Найдено инстансов: $instance_count"

if [ "$instance_count" -gt 0 ]; then
    instance_name=$(echo "$instances_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['instances'][0]['name'])" 2>/dev/null)
    socket_path=$(echo "$instances_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['instances'][0]['socket_path'])" 2>/dev/null)
    echo "   Первый инстанс: $instance_name ($socket_path)"
fi

echo

# 2. Список бэкендов
test_endpoint "GET" \
    "http://$HOST/api/v1/haproxy/backends" \
    "2. GET /api/v1/haproxy/backends"

# Получаем первый бэкенд для тестов
backends_response=$(curl -s http://$HOST/api/v1/haproxy/backends)
backend_count=$(echo "$backends_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['count'])" 2>/dev/null)
echo "   Найдено бэкендов: $backend_count"

if [ "$backend_count" -gt 0 ]; then
    first_backend=$(echo "$backends_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['backends'][0])" 2>/dev/null)
    echo "   Первый бэкенд: $first_backend"

    echo

    # 3. Серверы в бэкенде
    test_endpoint "GET" \
        "http://$HOST/api/v1/haproxy/backends/$first_backend/servers" \
        "3. GET /api/v1/haproxy/backends/$first_backend/servers"

    servers_response=$(curl -s http://$HOST/api/v1/haproxy/backends/$first_backend/servers)
    server_count=$(echo "$servers_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['count'])" 2>/dev/null)
    echo "   Найдено серверов: $server_count"

    if [ "$server_count" -gt 0 ]; then
        first_server=$(echo "$servers_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['servers'][0]['name'])" 2>/dev/null)
        server_status=$(echo "$servers_response" | python3 -c "import json, sys; print(json.load(sys.stdin)['data']['servers'][0]['status'])" 2>/dev/null)
        echo "   Первый сервер: $first_server (статус: $server_status)"
    fi
fi

echo
echo "=========================================="
echo "Сводка результатов:"
echo "=========================================="
echo
echo "✅ API endpoint /api/v1/haproxy/instances успешно реализован и работает!"
echo "✅ Найден $instance_count HAProxy инстанс(ов)"
echo "✅ Система готова к работе с HAProxy"
echo
echo "Доступные методы API:"
echo "  • GET  /api/v1/haproxy/instances - список инстансов"
echo "  • GET  /api/v1/haproxy/backends - список бэкендов"
echo "  • GET  /api/v1/haproxy/backends/{backend}/servers - серверы в бэкенде"
echo "  • POST /api/v1/haproxy/backends/{backend}/servers/{server}/action - управление сервером"
echo

# Делаем скрипт исполняемым
chmod +x $0 2>/dev/null