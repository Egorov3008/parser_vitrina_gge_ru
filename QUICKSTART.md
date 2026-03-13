# Быстрый старт

## За 5 минут

### 1. Установить зависимости

```bash
cd /home/claude/vitrina-parser
pip install -r requirements.txt
playwright install chromium
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
nano .env  # или вашего любимого редактора
```

**Минимальная конфигурация:**

```env
VITRINA_LOGIN=your_email@example.com
VITRINA_PASSWORD=your_password

TELEGRAM_BOT_TOKEN=1234567890:AAExampleToken
TELEGRAM_CHAT_ID=-1001234567890
```

**Как получить Telegram BotToken и ChatID:**
- Создать бота у [@BotFather](https://t.me/botfather) — получите `TELEGRAM_BOT_TOKEN`
- Открыть чат с ботом и получить его ID (например через `/start` и проверку логов)
- Для получения `TELEGRAM_CHAT_ID` группы: добавить бота в группу, отправить сообщение и найти ID в логах

### 3. Первый запуск с немедленной проверкой

```bash
RUN_ON_START=true HEADLESS=false python -m src.main
```

**Флаги:**
- `RUN_ON_START=true` — запустить парсер сразу при старте
- `HEADLESS=false` — показать браузер (для отладки авторизации)

### 4. Проверить результаты

После выполнения:
1. Проверить БД: `sqlite3 data/vitrina.db "SELECT COUNT(*) FROM projects;"`
2. Проверить логи: `tail logs/parser-*.log`
3. В Telegram чате должны прийти уведомления о найденных проектах

## Типичные проблемы

### ❌ Ошибка авторизации

**Симптом:** `Login failed - still on login page`

**Решение:**
1. Проверить корректность login/password в `.env`
2. Запустить с `HEADLESS=false` чтобы увидеть браузер
3. Проверить селекторы формы входа в `src/browser/session.py` (строки 88-94)
4. Возможно сайт изменил HTML структуру — обновить селекторы

### ❌ БД ошибка

**Симптом:** `No such table: projects`

**Решение:**
```bash
# Удалить старую БД
rm data/vitrina.db

# БД будет создана автоматически при следующем запуске
python -m src.main
```

### ❌ Telegram не получает уведомления

**Симптом:** Логи говорят что уведомления отправлены, но в Telegram ничего

**Решение:**
1. Проверить `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`
2. Убедиться что бот добавлен в чат (если группа)
3. Проверить логи на ошибки: `grep "Error sending" logs/parser-*.log`

### ❌ Браузер не запускается

**Симптом:** `Failed to initialize browser`

**Решение:**
```bash
# Переустановить chromium
playwright install chromium --with-deps

# На Linux может потребоваться:
sudo apt-get install -y libgtk-3-0
```

## Регулярный запуск

### На Linux (cron)

```bash
# Добавить в crontab
0 6 * * * cd /home/claude/vitrina-parser && python -m src.main >> logs/cron.log 2>&1
```

### На Windows (Task Scheduler)

1. Открыть "Планировщик задач"
2. Создать задачу
3. Action: `python -m src.main`
4. Working directory: `C:\path\to\vitrina-parser`

### Через systemd (Linux)

Создать `/etc/systemd/system/vitrina-parser.service`:

```ini
[Unit]
Description=Vitrina Parser
After=network.target

[Service]
Type=simple
User=claude
WorkingDirectory=/home/claude/vitrina-parser
Environment="PATH=/home/claude/vitrina-parser/venv/bin"
ExecStart=/home/claude/vitrina-parser/venv/bin/python -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl enable vitrina-parser
sudo systemctl start vitrina-parser
sudo systemctl status vitrina-parser
```

## Полезные команды

```bash
# Просмотр логов в реальном времени
tail -f logs/parser-$(date +%Y-%m-%d).log

# Статистика проектов
sqlite3 data/vitrina.db "SELECT category, COUNT(*) as count FROM projects GROUP BY category;"

# Очистить БД (внимание!)
sqlite3 data/vitrina.db "DELETE FROM projects; DELETE FROM run_logs;"

# Тестирование авторизации
HEADLESS=false python -c "
import asyncio
from src.browser.session import SessionManager

async def test():
    session = SessionManager()
    await session.initialize()
    await session.login()
    print('✅ Login successful!')
    await session.close()

asyncio.run(test())
"
```

## Следующие шаги

1. **Отладить селекторы** — если парсинг не работает, посмотрите селекторы в `src/services/projects.py`
2. **Настроить фильтры** — отредактируйте `FILTER_CATEGORIES`, `FILTER_REGIONS`, `FILTER_DAYS_BACK` в `.env`
3. **Добавить больше логирования** — используйте `logger.info()` / `logger.debug()` в своих местах

Удачи! 🚀
