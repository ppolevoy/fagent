#!/bin/bash
# Тестовый скрипт для нового endpoint /api/v1/haproxy/instances

# Настройки
HOST="${1:-192.168.8.88:11011}"

echo "============================================"
echo "Тестирование HAProxy Instances API Endpoint"
echo "Host: $HOST"
echo "============================================"
echo

# 1. Тест: Получение списка инстансов
echo "1. GET /api/v1/haproxy/instances"
echo "--------------------------------"
response=$(curl -s http://$HOST/api/v1/haproxy/instances)

if [ $? -eq 0 ]; then
    echo "$response" | python3 -m json.tool 2>/dev/null

    if [ $? -eq 0 ]; then
        # Проверяем успешность ответа
        success=$(echo "$response" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('success', False))" 2>/dev/null)

        if [ "$success" = "True" ]; then
            echo
            echo "✓ Тест пройден: Endpoint вернул успешный ответ"

            # Выводим информацию об инстансах
            echo
            echo "Найденные инстансы:"
            echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for inst in data['data']['instances']:
    status = '✓' if inst['available'] else '✗'
    print(f\"  {status} {inst['name']}: {inst['socket_path']}\")
"
        else
            echo
            echo "✗ Тест НЕ пройден: Endpoint вернул ошибку"
            error=$(echo "$response" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('error', 'Unknown error'))" 2>/dev/null)
            echo "  Ошибка: $error"
            echo
            echo "Возможные причины:"
            echo "  1. Новый код еще не применен на сервере"
            echo "  2. Агент нужно перезапустить"
            echo "  3. Ошибка в коде контроллера"
        fi
    else
        echo
        echo "✗ Ошибка: Ответ не является валидным JSON"
        echo "Сырой ответ: $response"
    fi
else
    echo "✗ Ошибка: Не удалось подключиться к $HOST"
    echo "Проверьте, что агент запущен и доступен"
fi

echo
echo "============================================"
echo "Дополнительные тесты"
echo "============================================"
echo

# 2. Тест: Проверка, что старые endpoints работают
echo "2. Проверка совместимости с существующими endpoints"
echo "----------------------------------------------------"

# Проверяем /backends
echo -n "GET /api/v1/haproxy/backends: "
backends_response=$(curl -s http://$HOST/api/v1/haproxy/backends)
backends_success=$(echo "$backends_response" | python3 -c "import json, sys; data = json.load(sys.stdin); print(data.get('success', False))" 2>/dev/null)

if [ "$backends_success" = "True" ]; then
    echo "✓ Работает"
    backends=$(echo "$backends_response" | python3 -c "import json, sys; data = json.load(sys.stdin); print(', '.join(data['data']['backends']))" 2>/dev/null)
    echo "  Найденные бэкенды: $backends"
else
    echo "✗ Ошибка"
fi

echo
echo "============================================"
echo "Инструкции по применению изменений"
echo "============================================"
echo
echo "Если endpoint /api/v1/haproxy/instances не работает:"
echo
echo "1. Подключитесь к серверу: ssh user@192.168.8.88"
echo "2. Перейдите в директорию проекта: cd /path/to/FAgent/project"
echo "3. Остановите агент: kill \$(pgrep -f main.py)"
echo "4. Запустите агент заново: python3.11 main.py &"
echo "5. Запустите этот тест снова: ./test_instances_endpoint.sh"
echo

# Делаем скрипт исполняемым
chmod +x $0 2>/dev/null