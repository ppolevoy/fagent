#!/bin/bash

# Скрипт для переключения между docker-py и subprocess версиями Docker плагинов

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGINS_DIR="$SCRIPT_DIR/plugins"
INTEGRATIONS_DIR="$SCRIPT_DIR/integrations"

show_help() {
    cat << EOF
Использование: $0 [VERSION]

VERSION:
    py        - Переключиться на docker-py версию (по умолчанию, требует библиотеку docker)
    ps        - Переключиться на subprocess версию (работает через Docker CLI)
    status    - Показать текущую версию
    help      - Показать эту справку

Примеры:
    $0 py      # Переключиться на docker-py версию
    $0 ps      # Переключиться на subprocess версию
    $0 status  # Проверить текущую версию

EOF
}

check_current_version() {
    if [ -f "$PLUGINS_DIR/docker_client.py" ]; then
        if grep -q "docker.from_env" "$PLUGINS_DIR/docker_client.py" 2>/dev/null; then
            echo "docker-py"
        elif grep -q "subprocess.run" "$PLUGINS_DIR/docker_client.py" 2>/dev/null; then
            echo "subprocess"
        else
            echo "unknown"
        fi
    else
        echo "not_installed"
    fi
}

show_status() {
    current=$(check_current_version)

    echo "=== Docker Plugins Version Status ==="
    echo ""

    case "$current" in
        "docker-py")
            echo "✓ Текущая версия: docker-py (через библиотеку docker)"
            echo "  Файлы:"
            echo "    - plugins/docker_client.py (docker-py)"
            echo "    - plugins/docker_discoverer.py (docker-py)"
            echo ""
            echo "  Производительность: ⚡ Очень быстро"
            echo "  Зависимости: Требует docker>=7.0.0"
            ;;
        "subprocess")
            echo "✓ Текущая версия: subprocess (через Docker CLI)"
            echo "  Файлы:"
            echo "    - plugins/docker_client.py (subprocess)"
            echo "    - plugins/docker_discoverer.py (subprocess)"
            echo ""
            echo "  Производительность: 🐢 Медленно"
            echo "  Зависимости: Только Docker CLI"
            ;;
        "unknown")
            echo "⚠ Версия не определена (возможно кастомная модификация)"
            ;;
        "not_installed")
            echo "✗ Docker плагины не установлены"
            ;;
    esac
    echo ""
}

switch_to_py() {
    echo "=== Переключение на docker-py версию ==="
    echo ""

    current=$(check_current_version)

    if [ "$current" = "docker-py" ]; then
        echo "✓ Уже используется docker-py версия"
        return 0
    fi

    # Бэкап текущих файлов
    if [ -f "$PLUGINS_DIR/docker_client.py" ]; then
        echo "1. Создание бэкапа текущих плагинов..."
        cp "$PLUGINS_DIR/docker_client.py" "$PLUGINS_DIR/docker_client.py.backup"
        cp "$PLUGINS_DIR/docker_discoverer.py" "$PLUGINS_DIR/docker_discoverer.py.backup"
        echo "   ✓ Бэкап создан"
    fi

    # Копирование docker-py версии
    echo "2. Установка docker-py версии..."
    if [ -f "$INTEGRATIONS_DIR/docker_client_dockerpy.py" ]; then
        cp "$INTEGRATIONS_DIR/docker_client_dockerpy.py" "$PLUGINS_DIR/docker_client.py"
        echo "   ✓ docker_client.py установлен"
    else
        echo "   ⚠ docker_client_dockerpy.py не найден в integrations/"
        return 1
    fi

    # docker_discoverer.py такой же для обеих версий, только импорт меняется
    # Текущая версия в plugins/ уже подходит
    echo "   ✓ docker-py версия установлена"

    echo "3. Проверка зависимостей..."
    if python3.11 -c "import docker" 2>/dev/null; then
        echo "   ✓ Библиотека docker установлена"
    else
        echo "   ⚠ Библиотека docker НЕ установлена"
        echo "   Установка: python3.11 -m pip install --break-system-packages docker>=7.0.0"
    fi

    echo ""
    echo "✓ Переключение завершено. Перезапустите агент."
}

switch_to_ps() {
    echo "=== Переключение на subprocess версию ==="
    echo ""

    current=$(check_current_version)

    if [ "$current" = "subprocess" ]; then
        echo "✓ Уже используется subprocess версия"
        return 0
    fi

    # Бэкап текущих файлов
    echo "1. Создание бэкапа текущих плагинов..."
    cp "$PLUGINS_DIR/docker_client.py" "$PLUGINS_DIR/docker_client.py.backup"
    cp "$PLUGINS_DIR/docker_discoverer.py" "$PLUGINS_DIR/docker_discoverer.py.backup"
    echo "   ✓ Бэкап создан"

    # Копирование subprocess версии
    echo "2. Установка subprocess версии..."
    cp "$INTEGRATIONS_DIR/docker_client_ps.py" "$PLUGINS_DIR/docker_client.py"
    cp "$INTEGRATIONS_DIR/docker_discoverer_ps.py" "$PLUGINS_DIR/docker_discoverer.py"
    echo "   ✓ subprocess версия установлена"

    echo "3. Проверка Docker CLI..."
    if docker version >/dev/null 2>&1; then
        echo "   ✓ Docker CLI доступен"
    else
        echo "   ✗ Docker CLI недоступен!"
        echo "   Установите Docker или проверьте права доступа"
    fi

    echo ""
    echo "✓ Переключение завершено. Перезапустите агент."
}

# Main
case "${1:-status}" in
    py|docker-py)
        switch_to_py
        ;;
    ps|subprocess)
        switch_to_ps
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "✗ Неизвестная команда: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
