# Server Deployment Guide

Руководство по развертыванию парсера Vitrina на сервере.

## Варианты запуска

### 1. Docker (рекомендуется) ⭐

**Преимущества:**
- 📦 Изолированное окружение
- 🔄 Легкое обновление
- 🛡️ Безопасность
- 📝 Версионирование конфигурации

**Запуск:**

```bash
# Клонировать репозиторий
git clone <repository-url>
cd vitrina-parser

# Настроить .env
cp .env.example .env
nano .env

# Запустить контейнер
docker-compose up -d

# Проверить статус
docker-compose ps

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

**Обновление:**

```bash
# Получить новые изменения
git pull

# Пересобрать и перезапустить
docker-compose up -d --build

# Очистить старые образы
docker image prune -f
```

**Конфигурация:**

| Параметр | Значение |
|----------|----------|
| Image | Python 3.11-slim |
| Working Dir | `/app` |
| Volumes | `./data:/app/data`, `./logs:/app/logs` |
| Env File | `.env` (read-only) |

---

### 2. systemd (Linux сервис)

**Преимущества:**
- ⚡ Автозапуск при старте системы
- 🔄 Автоматический перезапуск при сбоях
- 📊 Интеграция с journalctl
- 🔧 Стандартный механизм Linux

**Установка:**

```bash
# Клонировать репозиторий
cd /opt
git clone <repository-url> vitrina-parser
cd vitrina-parser

# Создать виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
playwright install chromium

# Настроить .env
cp .env.example .env
nano .env

# Установить системные зависимости для браузера
chmod +x install_browser_deps.sh
sudo bash install_browser_deps.sh
```

**Настройка сервиса:**

```bash
# Скопировать файл сервиса
sudo cp systemd/vitrina-parser.service /etc/systemd/system/

# Отредактировать путь (если нужно)
sudo nano /etc/systemd/system/vitrina-parser.service

# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable vitrina-parser

# Запустить
sudo systemctl start vitrina-parser

# Проверить статус
sudo systemctl status vitrina-parser
```

**Управление:**

```bash
# Старт
sudo systemctl start vitrina-parser

# Остановка
sudo systemctl stop vitrina-parser

# Перезапуск
sudo systemctl restart vitrina-parser

# Перезагрузка конфига
sudo systemctl daemon-reload

# Статус
sudo systemctl status vitrina-parser

# Журнал
journalctl -u vitrina-parser -f

# Журнал за сегодня
journalctl -u vitrina-parser --since today
```

**Файл сервиса:**

```ini
[Unit]
Description=Vitrina Parser Bot
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/vitrina-parser
Environment="PATH=/opt/vitrina-parser/venv/bin"
ExecStart=/opt/vitrina-parser/venv/bin/python -m src.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vitrina-parser

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

---

### 3. Прямой запуск (development)

**Преимущества:**
- 🔍 Отладка
- 🧪 Тестирование
- ⚡ Быстрый старт

**Запуск:**

```bash
# Активировать venv
source venv/bin/activate

# Запустить
python -m src.main

# Или с немедленным запуском
RUN_ON_START=true HEADLESS=false python -m src.main
```

**В фоне (nohup):**

```bash
nohup python -m src.main > parser.log 2>&1 &

# Проверить процесс
ps aux | grep parser

# Остановить
kill $(pgrep -f "src.main")
```

---

### 4. Cron (периодический запуск)

**Преимущества:**
- ⏰ Запуск по расписанию
- 💾 Минимальное потребление ресурсов
- 🔧 Простота настройки

**Настройка:**

```bash
# Открыть crontab
crontab -e

# Добавить задачу (запуск каждый день в 6:00)
0 6 * * * cd /opt/vitrina-parser && /opt/vitrina-parser/venv/bin/python -m src.main >> logs/cron.log 2>&1
```

**Примеры расписаний:**

```bash
# Каждый день в 6:00 UTC
0 6 * * *

# Каждый час
0 * * * *

# Каждые 4 часа
0 */4 * * *

# По будням в 9:00
0 9 * * 1-5

# Каждое воскресенье в полночь
0 0 * * 0
```

**Важно:** При использовании cron бот не работает постоянно, только выполняет парсинг по расписанию.

---

## Структура проекта

```
vitrina-parser/
├── src/
│   ├── main.py              # Точка входа
│   ├── config.py            # Конфигурация
│   ├── browser/             # Browser automation
│   ├── services/            # Business logic
│   ├── db/                  # Database layer
│   └── utils/               # Helpers
├── data/                    # SQLite database
├── logs/                    # Log files
├── venv/                    # Python virtual environment
├── systemd/                 # systemd service file
├── docker-compose.yml       # Docker configuration
├── Dockerfile               # Docker image
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables
└── .env.example             # Environment template
```

---

## Тома и хранение данных

### Docker volumes

| Том | Описание | Путь в контейнере |
|-----|----------|-------------------|
| `./data` | SQLite база данных | `/app/data` |
| `./logs` | Лог файлы | `/app/logs` |
| `./.env` | Конфигурация | `/app/.env` (read-only) |

### Хранение данных

**База данных:**
- Путь: `data/vitrina.db`
- Таблицы: `projects`, `run_logs`, `parser_settings`, `admins`, `notification_chats`, `credentials`
- Резервное копирование: копировать файл `.db`

**Логи:**
- Путь: `logs/parser-YYYY-MM-DD.log`
- Ротация: ежедневная
- Очистка: вручную или скриптом

---

## Конфигурация

### Минимальная конфигурация (.env)

```env
# Портал
VITRINA_URL=https://vitrina.gge.ru
VITRINA_LOGIN=your_email@example.com
VITRINA_PASSWORD=your_password

# Telegram
TELEGRAM_BOT_TOKEN=1234567890:AAExampleToken
TELEGRAM_CHAT_ID=-1001234567890

# Администраторы
ADMIN_ID=123456789

# Расписание
CRON_SCHEDULE=0 6 * * *

# Опционально
RUN_ON_START=false
HEADLESS=true
LOG_LEVEL=INFO
```

### Переменные окружения

| Переменная | Обязательная | Описание | По умолчанию |
|------------|--------------|----------|--------------|
| `VITRINA_URL` | Нет | URL портала | `https://vitrina.gge.ru` |
| `VITRINA_LOGIN` | **Да** | Логин для портала | - |
| `VITRINA_PASSWORD` | **Да** | Пароль для портала | - |
| `TELEGRAM_BOT_TOKEN` | **Да** | Токен Telegram бота | - |
| `TELEGRAM_CHAT_ID` | Нет | ID чата для уведомлений | - |
| `ADMIN_ID` | Нет | ID администраторов | - |
| `CRON_SCHEDULE` | Нет | Расписание (cron) | `0 6 * * *` |
| `DB_PATH` | Нет | Путь к БД | `./data/vitrina.db` |
| `RUN_ON_START` | Нет | Запуск при старте | `false` |
| `HEADLESS` | Нет | Режим браузера | `true` |
| `LOG_LEVEL` | Нет | Уровень логов | `INFO` |
| `LOG_DIR` | Нет | Папка логов | `./logs` |

---

## Мониторинг

### Проверка статуса

**Docker:**
```bash
docker-compose ps
docker-compose logs -f
```

**systemd:**
```bash
sudo systemctl status vitrina-parser
journalctl -u vitrina-parser -f
```

**Прямой запуск:**
```bash
ps aux | grep parser
tail -f logs/parser-*.log
```

### Проверка работы

```bash
# Количество проектов в БД
sqlite3 data/vitrina.db "SELECT COUNT(*) FROM projects;"

# Последний запуск
sqlite3 data/vitrina.db "SELECT * FROM run_logs ORDER BY id DESC LIMIT 1;"

# Настройки
sqlite3 data/vitrina.db "SELECT key, value FROM parser_settings;"

# Активные чаты
sqlite3 data/vitrina.db "SELECT chat_id FROM notification_chats WHERE is_active=1;"
```

### Логирование

**Просмотр логов:**

```bash
# Сегодняшние логи
tail -f logs/parser-$(date +%Y-%m-%d).log

# Вчерашние логи
tail -f logs/parser-$(date -d yesterday +%Y-%m-%d).log

# Поиск ошибок
grep "ERROR" logs/parser-*.log

# Поиск успешных запусков
grep "Запуск парсера" logs/parser-*.log
```

**Уровни логирования:**

| Уровень | Описание |
|---------|----------|
| `DEBUG` | Детальная информация для отладки |
| `INFO` | Основные события |
| `WARNING` | Предупреждения |
| `ERROR` | Ошибки |
| `CRITICAL` | Критические ошибки |

---

## Безопасность

### Файловые разрешения

```bash
# Владелец
sudo chown -R www-data:www-data /opt/vitrina-parser

# Права на директорию с БД
chmod 750 /opt/vitrina-parser/data

# Права на .env (конфиденциально)
chmod 600 /opt/vitrina-parser/.env
```

### Сетевая безопасность

- Бот не открывает портов наружу
- Соединение только исходящее (Telegram API, vitrina.gge.ru)
- Рекомендуется использовать firewall

### Резервное копирование

```bash
# Скрипт backup.sh
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/vitrina-parser"

mkdir -p $BACKUP_DIR

# Копировать БД
cp /opt/vitrina-parser/data/vitrina.db $BACKUP_DIR/vitrina-$DATE.db

# Копировать логи (опционально)
tar -czf $BACKUP_DIR/logs-$DATE.tar.gz /opt/vitrina-parser/logs/

# Удалить старые бэкапы (>30 дней)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

**Cron для бэкапа:**
```bash
# Каждый день в 3:00
0 3 * * * /opt/vitrina-parser/backup.sh
```

---

## Обновление

### Docker

```bash
# Получить изменения
git pull

# Пересобрать образ
docker-compose build

# Перезапустить контейнер
docker-compose up -d

# Проверить логи
docker-compose logs -f
```

### systemd

```bash
# Остановить сервис
sudo systemctl stop vitrina-parser

# Получить изменения
cd /opt/vitrina-parser
git pull

# Обновить зависимости
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Запустить сервис
sudo systemctl start vitrina-parser

# Проверить статус
sudo systemctl status vitrina-parser
```

### Откат версии

```bash
# Git откат
git checkout <previous-commit>

# Пересобрать/перезапустить
# (см. выше)
```

---

## Troubleshooting

### Сервис не запускается

**Проверка:**
```bash
sudo systemctl status vitrina-parser
journalctl -u vitrina-parser -n 50
```

**Возможные причины:**
- Неправильный путь в `.service` файле
- Отсутствуют зависимости браузера
- Ошибка в `.env`

---

### Ошибка браузера

**Симптом:** `Failed to initialize browser`

**Решение:**
```bash
# Переустановить Playwright
source venv/bin/activate
pip uninstall -y playwright
pip install playwright
playwright install chromium

# Установить системные зависимости
sudo bash install_browser_deps.sh
```

---

### Бот не отвечает

**Проверка:**
1. Проверить токен бота в `.env`
2. Проверить подключение к Telegram API
3. Проверить логи на ошибки

**Решение:**
```bash
# Перезапустить сервис
sudo systemctl restart vitrina-parser

# Проверить логи
journalctl -u vitrina-parser -f
```

---

### Заполняется диск логами

**Решение:**
```bash
# Очистить старые логи
find logs/ -name "parser-*.log" -mtime +30 -delete

# Настроить ротацию (logrotate)
sudo nano /etc/logrotate.d/vitrina-parser
```

**logrotate конфигурация:**
```
/opt/vitrina-parser/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data www-data
}
```

---

### Ошибка авторизации на портале

**Симптом:** `Login failed`

**Решение:**
1. Проверить логин/пароль в `.env`
2. Проверить доступность портала
3. Запустить с `HEADLESS=false` для отладки
4. Обновить селекторы в `src/browser/session.py`

---

## Производительность

### Требования к ресурсам

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| CPU | 1 core | 2 cores |
| RAM | 512 MB | 1 GB |
| Disk | 1 GB | 5 GB |
| Network | 1 Mbps | 10 Mbps |

### Оптимизация

**Для больших объемов:**
- Увеличить `limit` в `fetch_list()`
- Использовать кэширование
- Параллельные запросы для деталей проектов

**Мониторинг ресурсов:**
```bash
# Использование памяти
ps aux | grep parser

# Использование CPU
top -p $(pgrep -f "src.main")
```

---

## Интеграция

### Webhook (опционально)

Для мгновенных уведомлений можно настроить webhook:

```python
# В config.py добавить
webhook_url: str = ""

# В main.py настроить webhook
await bot.set_webhook(url=config.webhook_url)
```

### API (будущая версия)

Планируется REST API для:
- Получения списка проектов
- Управления настройками
- Статистики

---

## См. также

- [README.md](./README.md) — основная документация
- [ADMIN_PANEL.md](./ADMIN_PANEL.md) — админ-панель
- [QUICKSTART.md](./QUICKSTART.md) — быстрый старт
- [BROWSER_SETUP.md](./BROWSER_SETUP.md) — настройка браузера
