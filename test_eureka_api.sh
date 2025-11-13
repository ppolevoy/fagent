#!/bin/bash
# Тестовый скрипт для Eureka API
# Использование: ./test_eureka_api.sh [host:port]

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Хост агента (по умолчанию localhost:11011)
AGENT_HOST="${1:-localhost:11011}"
BASE_URL="http://${AGENT_HOST}/api/v1/eureka"

echo "=========================================="
echo "Тестирование Eureka API"
echo "Хост: $AGENT_HOST"
echo "=========================================="
echo ""

# Функция для красивого вывода результатов
function test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4

    echo -e "${YELLOW}TEST:${NC} $description"
    echo "  ${method} ${BASE_URL}${endpoint}"

    if [ -n "$data" ]; then
        echo "  Data: $data"
    fi

    if [ "$method" == "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "${BASE_URL}${endpoint}")
    else
        response=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Content-Type: application/json" \
            -d "$data" \
            "${BASE_URL}${endpoint}")
    fi

    # Разделяем тело ответа и HTTP код
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$http_code" == "200" ]; then
        echo -e "  ${GREEN}✓ HTTP $http_code${NC}"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    else
        echo -e "  ${RED}✗ HTTP $http_code${NC}"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
    fi

    echo ""
}

# 1. Получить список всех приложений
test_endpoint "GET" "/apps" "" "Get all applications from Eureka"

# 2. Сохраняем первое приложение для последующих тестов
FIRST_APP=$(curl -s "${BASE_URL}/apps" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('success') and data.get('data', {}).get('applications'):
        apps = data['data']['applications']
        if apps:
            print(apps[0]['instance_id'])
except:
    pass
" 2>/dev/null)

if [ -n "$FIRST_APP" ]; then
    echo -e "${GREEN}Найдено приложение для тестов: $FIRST_APP${NC}"
    echo ""

    # URL-encode instance_id (заменяем : на %3A)
    INSTANCE_ID_ENCODED=$(echo "$FIRST_APP" | sed 's/:/%3A/g')

    # 3. Получить информацию о конкретном приложении
    test_endpoint "GET" "/apps/${INSTANCE_ID_ENCODED}" "" "Get specific application info"

    # 4. Health check
    test_endpoint "GET" "/apps/${INSTANCE_ID_ENCODED}/health" "" "Check application health"

    # 5. Изменить log level (только показываем пример, не выполняем)
    echo -e "${YELLOW}EXAMPLE (not executed):${NC} Change log level to DEBUG"
    echo "  POST ${BASE_URL}/apps/${INSTANCE_ID_ENCODED}/loglevel"
    echo '  Data: {"logger": "ROOT", "level": "DEBUG"}'
    echo ""

    # 6. Shutdown (только показываем пример, не выполняем)
    echo -e "${YELLOW}EXAMPLE (not executed):${NC} Graceful shutdown"
    echo "  POST ${BASE_URL}/apps/${INSTANCE_ID_ENCODED}/shutdown"
    echo ""

    echo -e "${YELLOW}Чтобы выполнить команды управления, раскомментируйте строки в скрипте:${NC}"
    echo ""
    echo "# Изменить log level:"
    echo "# test_endpoint \"POST\" \"/apps/${INSTANCE_ID_ENCODED}/loglevel\" '{\"logger\": \"ROOT\", \"level\": \"DEBUG\"}' \"Set log level to DEBUG\""
    echo ""
    echo "# Graceful shutdown:"
    echo "# test_endpoint \"POST\" \"/apps/${INSTANCE_ID_ENCODED}/shutdown\" \"\" \"Shutdown application\""
    echo ""

else
    echo -e "${RED}Приложения не найдены в Eureka${NC}"
    echo "Убедитесь что:"
    echo "  1. EUREKA_DISCOVERY_ENABLED=true"
    echo "  2. Eureka сервер доступен"
    echo "  3. В Eureka зарегистрированы приложения"
fi

echo "=========================================="
echo "Тестирование завершено"
echo "=========================================="
