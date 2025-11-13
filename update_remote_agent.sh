#!/bin/bash
# Скрипт для обновления HAProxy контроллера на удаленном сервере

# Настройки
REMOTE_HOST="${1:-192.168.8.88}"
REMOTE_USER="${2:-root}"  # Замените на ваш пользователь
REMOTE_PATH="${3:-/site/app/FAgent/project}"  # Путь к проекту на сервере

echo "============================================"
echo "Обновление HAProxy Controller на сервере"
echo "Host: $REMOTE_USER@$REMOTE_HOST"
echo "Path: $REMOTE_PATH"
echo "============================================"
echo

# Создаем временный файл с обновленным методом handle_get
cat > /tmp/haproxy_controller_patch.py << 'EOF'
# Это патч для добавления endpoint /api/v1/haproxy/instances
# Добавить в начало метода handle_get после строки 177:

            # Специальный endpoint для получения списка инстансов
            if first_part == 'instances' and len(path_parts) == 1:
                instances = self.get_instances()
                instances_info = []

                # Добавляем информацию о каждом инстансе
                for instance_name in instances:
                    client = self.clients[instance_name]
                    try:
                        # Проверяем доступность инстанса
                        is_available = client.health_check()
                        instances_info.append({
                            'name': instance_name,
                            'socket_path': client.socket_path,
                            'available': is_available
                        })
                    except Exception:
                        instances_info.append({
                            'name': instance_name,
                            'socket_path': client.socket_path,
                            'available': False
                        })

                return self._success_response({
                    'instances': instances_info,
                    'count': len(instances_info)
                })
EOF

echo "Опции обновления:"
echo "=================="
echo
echo "1. АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ (через SSH):"
echo "   Выполните эту команду (нужен SSH доступ):"
echo
echo "   scp controllers/haproxy_controller.py $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/controllers/"
echo
echo "2. РУЧНОЕ ОБНОВЛЕНИЕ:"
echo "   a) Подключитесь к серверу:"
echo "      ssh $REMOTE_USER@$REMOTE_HOST"
echo
echo "   b) Перейдите в директорию проекта:"
echo "      cd $REMOTE_PATH"
echo
echo "   c) Создайте резервную копию:"
echo "      cp controllers/haproxy_controller.py controllers/haproxy_controller.py.backup"
echo
echo "   d) Откройте файл для редактирования:"
echo "      vi controllers/haproxy_controller.py"
echo
echo "   e) Найдите строку 177 (first_part = path_parts[0])"
echo "      и добавьте после неё код из патча выше"
echo
echo "   f) Сохраните файл и перезапустите агент:"
echo "      # Остановить агент"
echo "      pkill -f main.py"
echo "      # Запустить агент"
echo "      cd $REMOTE_PATH && python3.11 main.py &"
echo
echo "3. ПРОВЕРКА ПОСЛЕ ОБНОВЛЕНИЯ:"
echo "   curl http://$REMOTE_HOST:11011/api/v1/haproxy/instances"
echo

# Проверяем, можем ли мы подключиться по SSH без пароля
echo "Проверка SSH подключения..."
if ssh -o BatchMode=yes -o ConnectTimeout=5 $REMOTE_USER@$REMOTE_HOST echo "SSH OK" 2>/dev/null; then
    echo "✓ SSH подключение доступно без пароля"
    echo
    read -p "Хотите автоматически скопировать обновленный файл? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Копирование файла..."
        if scp controllers/haproxy_controller.py $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/controllers/; then
            echo "✓ Файл успешно скопирован"
            echo
            echo "Перезапуск агента..."
            ssh $REMOTE_USER@$REMOTE_HOST "cd $REMOTE_PATH && pkill -f main.py; sleep 2; python3.11 main.py > /dev/null 2>&1 &"
            echo "✓ Агент перезапущен"
            echo
            sleep 3
            echo "Тестирование нового endpoint..."
            curl -s http://$REMOTE_HOST:11011/api/v1/haproxy/instances | python3 -m json.tool
        else
            echo "✗ Ошибка при копировании файла"
        fi
    fi
else
    echo "✗ SSH подключение требует пароля или недоступно"
    echo "  Используйте ручное обновление (вариант 2 выше)"
fi