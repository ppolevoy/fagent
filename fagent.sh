#!/bin/bash
#
# FAgent Service Control Script
# Управление Application Discovery Agent
#

# Определяем директорию скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Конфигурация
APP_NAME="FAgent"
MAIN_SCRIPT="main.py"
PID_FILE="$SCRIPT_DIR/.fagent.pid"
LOG_FILE="$SCRIPT_DIR/fagent.log"
PYTHON_CMD="python3.11"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция логирования
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка существования main.py
check_main_script() {
    if [ ! -f "$MAIN_SCRIPT" ]; then
        log_error "Main script not found: $MAIN_SCRIPT"
        exit 1
    fi
}

# Получение PID из файла
get_pid_from_file() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

# Проверка работает ли процесс
is_running() {
    local pid="$1"
    if [ -z "$pid" ]; then
        return 1
    fi

    # Проверяем существует ли процесс
    if ps -p "$pid" > /dev/null 2>&1; then
        # Проверяем что это действительно наш процесс
        if ps -p "$pid" -o args= | grep -q "$MAIN_SCRIPT"; then
            return 0
        fi
    fi
    return 1
}

# Поиск процесса по имени (если PID файл потерян)
find_process() {
    pgrep -f "$PYTHON_CMD.*$MAIN_SCRIPT" | head -1
}

# Запуск сервиса
start() {
    check_main_script

    # Проверяем не запущен ли уже
    local pid=$(get_pid_from_file)
    if is_running "$pid"; then
        log_warn "$APP_NAME is already running (PID: $pid)"
        return 0
    fi

    # Ищем процесс без PID файла
    pid=$(find_process)
    if [ -n "$pid" ]; then
        log_warn "$APP_NAME is already running (PID: $pid, PID file was missing)"
        echo "$pid" > "$PID_FILE"
        return 0
    fi

    # Запускаем сервис
    log_info "Starting $APP_NAME..."

    # Создаем лог файл если не существует
    touch "$LOG_FILE"

    # Запускаем в фоне
    nohup "$PYTHON_CMD" "$MAIN_SCRIPT" >> "$LOG_FILE" 2>&1 &
    local new_pid=$!

    # Сохраняем PID
    echo "$new_pid" > "$PID_FILE"

    # Ждем немного для проверки успешного запуска
    sleep 2

    if is_running "$new_pid"; then
        log_info "$APP_NAME started successfully (PID: $new_pid)"
        log_info "Log file: $LOG_FILE"
        return 0
    else
        log_error "$APP_NAME failed to start"
        rm -f "$PID_FILE"
        log_info "Check log file for details: $LOG_FILE"
        return 1
    fi
}

# Остановка сервиса
stop() {
    local pid=$(get_pid_from_file)

    # Если PID файла нет, ищем процесс
    if [ -z "$pid" ]; then
        pid=$(find_process)
    fi

    if [ -z "$pid" ]; then
        log_warn "$APP_NAME is not running"
        rm -f "$PID_FILE"
        return 0
    fi

    if ! is_running "$pid"; then
        log_warn "$APP_NAME is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 0
    fi

    log_info "Stopping $APP_NAME (PID: $pid)..."

    # Пытаемся graceful shutdown (SIGTERM)
    kill -TERM "$pid" 2>/dev/null

    # Ждем до 10 секунд
    local count=0
    while [ $count -lt 10 ]; do
        if ! is_running "$pid"; then
            log_info "$APP_NAME stopped successfully"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    # Если не остановился, используем SIGKILL
    log_warn "$APP_NAME did not stop gracefully, forcing shutdown..."
    kill -KILL "$pid" 2>/dev/null
    sleep 1

    if ! is_running "$pid"; then
        log_info "$APP_NAME force stopped"
        rm -f "$PID_FILE"
        return 0
    else
        log_error "Failed to stop $APP_NAME"
        return 1
    fi
}

# Перезапуск сервиса
restart() {
    log_info "Restarting $APP_NAME..."
    stop
    sleep 2
    start
}

# Статус сервиса
status() {
    local pid=$(get_pid_from_file)

    # Если PID файла нет, ищем процесс
    if [ -z "$pid" ]; then
        pid=$(find_process)
        if [ -n "$pid" ]; then
            log_warn "$APP_NAME is running but PID file is missing (PID: $pid)"
            echo "$pid" > "$PID_FILE"
            return 0
        fi
    fi

    if [ -z "$pid" ]; then
        log_info "$APP_NAME is not running"
        return 1
    fi

    if is_running "$pid"; then
        log_info "$APP_NAME is running (PID: $pid)"

        # Показываем дополнительную информацию
        echo ""
        echo "Process info:"
        ps -p "$pid" -o pid,ppid,user,%cpu,%mem,etime,cmd --no-headers

        # Проверяем порт
        local port=$(grep -E "^(export )?AGENT_PORT=" "$SCRIPT_DIR/config.py" 2>/dev/null | grep -oE "[0-9]+" | head -1)
        if [ -z "$port" ]; then
            port="11011"  # Default port
        fi

        echo ""
        if netstat -tlnp 2>/dev/null | grep -q ":$port.*$pid/"; then
            echo -e "${GREEN}✓${NC} Listening on port $port"
        else
            echo -e "${YELLOW}⚠${NC} Not listening on expected port $port"
        fi

        return 0
    else
        log_warn "$APP_NAME is not running (stale PID file)"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Просмотр логов
logs() {
    if [ ! -f "$LOG_FILE" ]; then
        log_warn "Log file not found: $LOG_FILE"
        return 1
    fi

    local lines="${1:-50}"
    log_info "Last $lines lines of $LOG_FILE:"
    echo ""
    tail -n "$lines" "$LOG_FILE"
}

# Просмотр логов в реальном времени
follow() {
    if [ ! -f "$LOG_FILE" ]; then
        log_warn "Log file not found: $LOG_FILE"
        return 1
    fi

    log_info "Following $LOG_FILE (Ctrl+C to stop)..."
    echo ""
    tail -f "$LOG_FILE"
}

# Очистка логов
clean_logs() {
    if [ -f "$LOG_FILE" ]; then
        log_info "Cleaning log file: $LOG_FILE"
        > "$LOG_FILE"
        log_info "Log file cleaned"
    else
        log_warn "Log file not found: $LOG_FILE"
    fi
}

# Тест API
test_api() {
    local pid=$(get_pid_from_file)
    if ! is_running "$pid"; then
        log_error "$APP_NAME is not running. Start it first with: $0 start"
        return 1
    fi

    local port=$(grep -E "^(export )?AGENT_PORT=" "$SCRIPT_DIR/config.py" 2>/dev/null | grep -oE "[0-9]+" | head -1)
    if [ -z "$port" ]; then
        port="11011"
    fi

    log_info "Testing API endpoints on port $port..."
    echo ""

    # Test /ping
    echo -n "  /ping: "
    if curl -s -f "http://localhost:$port/ping" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi

    # Test /app
    echo -n "  /app: "
    if curl -s -f "http://localhost:$port/app" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi

    # Test /api/v1/apps
    echo -n "  /api/v1/apps: "
    if curl -s -f "http://localhost:$port/api/v1/apps" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
    fi

    echo ""
    log_info "For detailed output, use: curl http://localhost:$port/api/v1/apps"
}

# Справка
usage() {
    cat << EOF
Usage: $0 {start|stop|restart|status|logs|follow|clean-logs|test|help}

Commands:
    start       - Start $APP_NAME service
    stop        - Stop $APP_NAME service
    restart     - Restart $APP_NAME service
    status      - Show service status
    logs [N]    - Show last N lines of logs (default: 50)
    follow      - Follow logs in real-time
    clean-logs  - Clean log file
    test        - Test API endpoints
    help        - Show this help message

Examples:
    $0 start            # Start the service
    $0 status           # Check if running
    $0 logs 100         # Show last 100 log lines
    $0 follow           # Watch logs in real-time
    $0 restart          # Restart the service
    $0 test             # Test API endpoints

Files:
    PID file: $PID_FILE
    Log file: $LOG_FILE
    Main script: $MAIN_SCRIPT

EOF
}

# Главная функция
main() {
    case "${1:-}" in
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        status)
            status
            ;;
        logs)
            logs "${2:-50}"
            ;;
        follow|tail)
            follow
            ;;
        clean-logs|clean)
            clean_logs
            ;;
        test)
            test_api
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log_error "Unknown command: ${1:-}"
            echo ""
            usage
            exit 1
            ;;
    esac
}

# Запуск
main "$@"
