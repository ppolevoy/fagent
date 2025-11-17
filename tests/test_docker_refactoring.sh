#!/bin/bash

echo "=== Docker Client Refactoring Test ==="
echo ""

# Запускаем агент
python3.11 main.py > /tmp/agent_test.log 2>&1 &
AGENT_PID=$!

echo "Starting agent (PID: $AGENT_PID)..."
sleep 12

# Проверяем что агент запустился
if curl -s http://localhost:11011/ping > /dev/null 2>&1; then
    echo "✓ Agent started successfully"
    echo ""

    # Тестируем Docker discovery
    echo "Testing Docker discovery..."
    curl -s http://localhost:11011/app | python3.11 << 'PYTHON_SCRIPT'
import json, sys

try:
    apps = json.load(sys.stdin)
    docker_apps = [a for a in apps if a.get('metadata', {}).get('source') == 'docker']

    print(f'✓ Successfully discovered {len(docker_apps)} Docker applications\n')

    for i, app in enumerate(docker_apps[:3], 1):
        meta = app['metadata']
        print(f'{i}. {app["name"]}')
        print(f'   Version: {app["version"]}')
        print(f'   Status: {app["status"]}')
        print(f'   Port: {meta["port"]}')
        print(f'   PID: {meta["pid"]}')
        print(f'   Image: {meta["image_full"]}')
        if meta.get('compose_project_dir'):
            print(f'   Compose: {meta["compose_project_dir"]}')
        print()

    if len(docker_apps) > 3:
        print(f'... and {len(docker_apps) - 3} more\n')

except Exception as e:
    print(f'✗ Error: {e}')
    sys.exit(1)
PYTHON_SCRIPT

    if [ $? -eq 0 ]; then
        echo "✓ Docker discovery test PASSED"
    else
        echo "✗ Docker discovery test FAILED"
    fi
else
    echo "✗ Agent failed to start"
    echo ""
    echo "Last 20 lines of log:"
    tail -20 /tmp/agent_test.log
fi

# Останавливаем агент
echo ""
echo "Stopping agent..."
kill $AGENT_PID 2>/dev/null
wait $AGENT_PID 2>/dev/null

echo "✓ Test completed"
