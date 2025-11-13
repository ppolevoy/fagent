# FAgent Control Script Documentation

## Overview

`fagent.sh` - удобный shell скрипт для управления Application Discovery Agent.

## Installation

Скрипт уже находится в директории проекта:
```bash
cd /site/app/FAgent/project
chmod +x fagent.sh
```

## Usage

```bash
./fagent.sh {command} [options]
```

## Commands

### Start Service
Запускает FAgent в фоновом режиме:
```bash
./fagent.sh start
```

**Выход:**
```
[INFO] Starting FAgent...
[INFO] FAgent started successfully (PID: 12345)
[INFO] Log file: /site/app/FAgent/project/fagent.log
```

**Особенности:**
- Проверяет не запущен ли уже сервис
- Создает PID файл для отслеживания процесса
- Перенаправляет вывод в лог файл
- Проверяет успешность запуска через 2 секунды

### Stop Service
Останавливает FAgent:
```bash
./fagent.sh stop
```

**Особенности:**
- Сначала отправляет SIGTERM (graceful shutdown)
- Ждет до 10 секунд завершения
- При необходимости использует SIGKILL (force stop)
- Удаляет PID файл после остановки

### Restart Service
Перезапускает FAgent:
```bash
./fagent.sh restart
```

Эквивалентно:
```bash
./fagent.sh stop
./fagent.sh start
```

### Status
Показывает статус сервиса:
```bash
./fagent.sh status
```

**Выход (если запущен):**
```
[INFO] FAgent is running (PID: 12345)

Process info:
 12345       1 root      0.6  0.3       00:05:23 python3.11 main.py

✓ Listening on port 11011
```

**Выход (если не запущен):**
```
[INFO] FAgent is not running
```

**Особенности:**
- Проверяет существование процесса по PID
- Показывает информацию о процессе (CPU, Memory, uptime)
- Проверяет прослушивается ли порт
- Восстанавливает PID файл если он был потерян

### Logs
Показывает последние N строк лога:
```bash
./fagent.sh logs [N]
```

**Примеры:**
```bash
./fagent.sh logs       # Последние 50 строк (по умолчанию)
./fagent.sh logs 100   # Последние 100 строк
./fagent.sh logs 10    # Последние 10 строк
```

### Follow Logs
Отслеживает логи в реальном времени:
```bash
./fagent.sh follow
```

Эквивалентно `tail -f fagent.log`. Нажмите `Ctrl+C` для выхода.

**Альтернативная команда:**
```bash
./fagent.sh tail
```

### Clean Logs
Очищает лог файл:
```bash
./fagent.sh clean-logs
```

**Особенности:**
- Не останавливает сервис
- Просто очищает содержимое файла (> fagent.log)

### Test API
Тестирует доступность API endpoints:
```bash
./fagent.sh test
```

**Выход:**
```
[INFO] Testing API endpoints on port 11011...

  /ping: ✓
  /app: ✓
  /api/v1/apps: ✓

[INFO] For detailed output, use: curl http://localhost:11011/api/v1/apps
```

**Проверяемые endpoints:**
- `/ping` - health check
- `/app` - старый формат API
- `/api/v1/apps` - новый формат API

### Help
Показывает справку:
```bash
./fagent.sh help
```

Альтернативы:
```bash
./fagent.sh --help
./fagent.sh -h
```

## Files

### PID File
**Путь:** `/site/app/FAgent/project/.fagent.pid`

Содержит PID запущенного процесса. Используется для:
- Проверки статуса
- Остановки сервиса
- Предотвращения повторного запуска

### Log File
**Путь:** `/site/app/FAgent/project/fagent.log`

Содержит все логи работы сервиса:
- Загрузка плагинов и контроллеров
- Обнаружение приложений
- HTTP запросы (опционально)
- Ошибки и предупреждения

## Common Workflows

### Первый запуск
```bash
# Запустить сервис
./fagent.sh start

# Проверить статус
./fagent.sh status

# Протестировать API
./fagent.sh test
```

### Просмотр логов при проблемах
```bash
# Посмотреть последние 50 строк
./fagent.sh logs

# Следить за логами в реальном времени
./fagent.sh follow
```

### Перезапуск после изменений конфигурации
```bash
# Перезапустить
./fagent.sh restart

# Проверить что все работает
./fagent.sh test
```

### Остановка перед обновлением
```bash
# Остановить
./fagent.sh stop

# Обновить код
git pull

# Запустить заново
./fagent.sh start
```

### Очистка логов при переполнении
```bash
# Посмотреть размер лога
ls -lh fagent.log

# Очистить если слишком большой
./fagent.sh clean-logs

# Или с архивацией
mv fagent.log fagent.log.$(date +%Y%m%d)
touch fagent.log
```

## Advanced Usage

### Запуск из cron
```bash
# Добавить в crontab для автозапуска при перезагрузке
@reboot /site/app/FAgent/project/fagent.sh start
```

### Мониторинг доступности
```bash
# Проверка каждые 5 минут
*/5 * * * * /site/app/FAgent/project/fagent.sh status || /site/app/FAgent/project/fagent.sh start
```

### Ротация логов через logrotate
```bash
# Создать /etc/logrotate.d/fagent
/site/app/FAgent/project/fagent.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 root root
    postrotate
        /site/app/FAgent/project/fagent.sh restart > /dev/null
    endscript
}
```

### Интеграция с systemd (опционально)
Для более глубокой интеграции с системой можно создать systemd service:

```bash
# /etc/systemd/system/fagent.service
[Unit]
Description=FAgent Application Discovery Service
After=network.target

[Service]
Type=forking
User=root
WorkingDirectory=/site/app/FAgent/project
ExecStart=/site/app/FAgent/project/fagent.sh start
ExecStop=/site/app/FAgent/project/fagent.sh stop
ExecReload=/site/app/FAgent/project/fagent.sh restart
PIDFile=/site/app/FAgent/project/.fagent.pid
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
systemctl daemon-reload
systemctl enable fagent
systemctl start fagent
systemctl status fagent
```

## Troubleshooting

### Сервис не запускается
1. Проверьте логи:
   ```bash
   ./fagent.sh logs 100
   ```

2. Проверьте не занят ли порт:
   ```bash
   netstat -tlnp | grep 11011
   ```

3. Проверьте права доступа:
   ```bash
   ls -l main.py fagent.sh
   ```

### Сервис запускается но не отвечает
1. Проверьте что процесс жив:
   ```bash
   ./fagent.sh status
   ```

2. Проверьте порт вручную:
   ```bash
   curl http://localhost:11011/ping
   ```

3. Проверьте логи на ошибки:
   ```bash
   ./fagent.sh logs | grep -i error
   ```

### PID файл потерян
Скрипт автоматически найдет процесс и восстановит PID файл:
```bash
./fagent.sh status
```

### Сервис не останавливается
Если `stop` не работает, используйте прямой kill:
```bash
# Найти PID
ps aux | grep "python.*main.py"

# Остановить принудительно
kill -9 <PID>

# Очистить PID файл
rm -f .fagent.pid
```

## Exit Codes

- `0` - Успешное выполнение
- `1` - Ошибка выполнения или сервис не запущен (для `status`)

## Security Considerations

- Скрипт требует прав для управления процессами
- PID файл доступен для чтения всем пользователям
- Лог файл может содержать чувствительную информацию
- Рекомендуется запускать от отдельного пользователя (не root)

## Performance Tips

- Регулярно очищайте старые логи
- Используйте logrotate для автоматической ротации
- Мониторьте размер PID и log файлов
- При высокой нагрузке рассмотрите вынос логов на отдельный диск

## See Also

- [CLAUDE.md](CLAUDE.md) - Полная документация проекта
- [HAPROXY_API.md](HAPROXY_API.md) - Документация HAProxy API
- [config.py](config.py) - Конфигурация приложения
