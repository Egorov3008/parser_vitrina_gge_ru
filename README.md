# Парсер Витрина Проектов

Автоматизированный парсер портала [vitrina.gge.ru](https://vitrina.gge.ru) для ежедневного мониторинга новых инвестиционных проектов с уведомлениями в Telegram.

## Функциональность

- 🔍 **Парсинг проектов** — автоматическая выборка новых объектов по настраиваемым фильтрам
- 📋 **Фильтрация** — по категориям, регионам, году экспертизы и дате публикации
- 📱 **Telegram уведомления** — информирование о новых проектах с полной информацией
- 📊 **Статистика** — отслеживание количества проектов и ошибок
- ⏱ **Гибкое расписание** — cron-выражения для запуска по расписанию
- 💾 **SQLite БД** — хранение информации о проектах и логах запусков
- ⚙️ **Админ-панель** — управление настройками через Telegram
- 👥 **Мульти-чат поддержка** — уведомления в несколько чатов одновременно
- 🔐 **Управление учетными данными** — хранение и смена логинов/паролей для портала
- 🛑 **Остановка парсера** — возможность остановить текущий запуск
- 📊 **Экспорт в Excel** — выгрузка проектов и проектировщиков в Excel-файлы

## Требования

- Python 3.11+
- Chromium браузер (для Playwright)
- Linux/macOS/Windows

## Установка

### 1. Клонировать репозиторий и перейти в директорию

```bash
cd vitrina-parser
```

### 2. Создать виртуальное окружение

```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
playwright install chromium
```

**Важно:** Если при запуске возникает ошибка `libnspr4.so: cannot open shared object file`, нужно установить системные зависимости браузера. Смотрите [BROWSER_SETUP.md](./BROWSER_SETUP.md) для подробных инструкций.

### 4. Настроить переменные окружения

```bash
cp .env.example .env
# Отредактировать .env с вашими учетными данными
nano .env
```

**Необходимые переменные:**

```env
# Авторизация на портале
VITRINA_URL=https://vitrina.gge.ru
VITRINA_LOGIN=your_email@example.com
VITRINA_PASSWORD=your_password

# Telegram бот (создать через @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:AAExampleToken
TELEGRAM_CHAT_ID=-1001234567890  # ID чата (с минусом для групп)

# Администраторы (доступ к админ-панели)
ADMIN_ID=123456789  # Ваш Telegram ID

# Расписание (cron, UTC)
CRON_SCHEDULE=0 6 * * *  # 6:00 UTC каждый день

# Запуск при старте
RUN_ON_START=false

# Опционально
HEADLESS=true
LOG_LEVEL=INFO
```

**Важно:** После первого запуска основные настройки (категории, регионы, год экспертизы, расписание, чаты) можно изменять через админ-панель в Telegram (`/admin`).

## Использование

### Запуск парсера

```bash
python -m src.main
```

Бот будет ждать команд в Telegram чате.

### Telegram команды

#### Основные команды:

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и список команд |
| `/status` | Информация о последнем запуске |
| `/run_now` | Запустить парсер немедленно |
| `/stop` | Остановить текущий запуск парсера |
| `/stats` | Статистика проектов и ошибок |
| `/help` | Справка по командам |
| `/getChatId` | Получить ID текущего чата |

#### Админ-панель:

| Команда | Описание |
|---------|----------|
| `/admin` | Открыть панель управления настройками |
| `/add_admin <id>` | Добавить администратора (только для админов) |

### Админ-панель

Админ-панель позволяет управлять настройками парсера прямо из Telegram:

- 📁 **Категории** — выбор категорий проектов для фильтрации (25 категорий)
- 📍 **Регионы** — выбор регионов России (все регионы РФ, 89 шт.)
- 📅 **Год экспертизы** — фильтр по году экспертизы проекта
- ⏰ **Расписание** — настройка cron-расписания для автоматического запуска
- 📱 **Чаты** — управление чатами для уведомлений (мульти-чат поддержка)
- 👥 **Администраторы** — управление списком администраторов
- 🔑 **Учетки** — управление учетными данными для портала
- 📊 **Экспорт в Excel** — выгрузка проектов и проектировщиков
- 🗑️ **Очистить данные** — очистка базы данных

**Как получить доступ:**
1. Добавьте свой Telegram ID в `.env` файл: `ADMIN_ID=123456789`
2. Перезапустите парсер
3. Отправьте команду `/admin`

**Узнать свой Telegram ID:** напишите боту [@userinfobot](https://t.me/userinfobot)

### Примеры

**Проверить последний запуск:**
```
/status
```

**Принудительно запустить парсер:**
```
/run_now
```

**Просмотреть статистику:**
```
/stats
```

**Остановить текущий парсер:**
```
/stop
```

**Открыть админ-панель:**
```
/admin
```

**Добавить администратора:**
```
/add_admin 123456789
```

**Получить ID чата:**
```
/getChatId
```

## Архитектура

```
src/
├── main.py              # Точка входа, Telegram бот (aiogram)
├── config.py            # Загрузка конфига из .env (Pydantic)
│
├── browser/
│   ├── session.py       # Управление браузер-сессией (Playwright)
│   └── scraper.py       # Вспомогательные методы DOM парсинга
│
├── services/
│   ├── projects.py      # Парсинг списка и деталей проектов
│   ├── telegram.py      # Отправка уведомлений в Telegram
│   ├── scheduler.py     # APScheduler и pipeline парсинга
│   ├── admin_panel.py   # Админ-панель для управления настройками
│   └── egrz.py          # Сервис для работы с ЕГРЗ
│
├── db/
│   ├── database.py      # Управление SQLite подключением
│   └── repository.py    # Работа с данными проектов и настроек
│
└── utils/
    ├── logger.py        # Loguru настройка
    └── formatters.py    # Форматирование сообщений Telegram
```

## Технологический стек

| Компонент | Пакет | Версия |
|-----------|-------|--------|
| Браузер | `playwright` | >=1.40.0 |
| Telegram бот | `aiogram` | >=3.0 |
| Планировщик | `apscheduler` | >=3.10.4 |
| Конфиг | `python-dotenv`, `pydantic-settings` | >=1.0, >=2.0 |
| Логирование | `loguru` | >=0.7.2 |
| HTTP | `httpx` | >=0.25.0 |
| Excel | `openpyxl` | >=3.1.0 |

## База данных

### Таблица `projects`

Хранит информацию о проектах:

```sql
CREATE TABLE projects (
  id              INTEGER PRIMARY KEY,
  vitrina_id      TEXT UNIQUE,          -- ID на портале
  expertise_num   TEXT,                 -- Номер экспертизы
  object_name     TEXT,                 -- Наименование объекта
  expert_org      TEXT,                 -- Экспертная организация
  developer       TEXT,                 -- Застройщик
  tech_customer   TEXT,                 -- Технический заказчик
  region          TEXT,                 -- Регион
  category        TEXT,                 -- Категория
  characteristics TEXT,                 -- JSON дополнительные поля
  published_at    TEXT,                 -- Дата публикации
  updated_at      TEXT,                 -- Дата обновления
  url             TEXT,                 -- Ссылка на проект
  notified_at     TEXT,                 -- Время отправки уведомления
  created_at      TEXT DEFAULT (now)    -- Добавлено в БД
);
```

### Таблица `run_logs`

Логирует каждый запуск парсера:

```sql
CREATE TABLE run_logs (
  id          INTEGER PRIMARY KEY,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  status      TEXT,       -- 'success' | 'error' | 'partial'
  new_count   INTEGER,    -- Количество новых проектов
  error_msg   TEXT        -- Сообщение об ошибке
);
```

### Таблица `parser_settings`

Хранит настройки парсера:

```sql
CREATE TABLE parser_settings (
  id          INTEGER PRIMARY KEY,
  key         TEXT UNIQUE,
  value       TEXT,         -- JSON значение
  description TEXT,
  updated_at  TEXT
);
```

**Ключи настроек:**
- `filter_categories` — выбранные категории (JSON array)
- `filter_regions` — выбранные регионы (JSON array)
- `expertise_year` — год экспертизы (integer)
- `cron_schedule` — cron-расписание (string)

### Таблица `notification_chats`

Чаты для отправки уведомлений:

```sql
CREATE TABLE notification_chats (
  id          INTEGER PRIMARY KEY,
  chat_id     TEXT UNIQUE,
  chat_name   TEXT,
  is_active   INTEGER DEFAULT 1,
  created_at  TEXT
);
```

### Таблица `admins`

Администраторы бота:

```sql
CREATE TABLE admins (
  id              INTEGER PRIMARY KEY,
  telegram_id     TEXT UNIQUE,
  username        TEXT,
  created_at      TEXT
);
```

### Таблица `credentials`

Учетные данные для портала:

```sql
CREATE TABLE credentials (
  id          INTEGER PRIMARY KEY,
  login       TEXT,
  password    TEXT,
  label       TEXT,
  is_active   INTEGER DEFAULT 0,
  created_at  TEXT
);
```

## Логирование

Логи сохраняются в `logs/parser-YYYY-MM-DD.log` с ротацией по дням.

Уровни логирования настраиваются через `LOG_LEVEL` в `.env`:
- `DEBUG` — детальная информация
- `INFO` — основные события
- `WARNING` — предупреждения
- `ERROR` — ошибки
- `CRITICAL` — критические ошибки

## Документация

| Файл | Описание |
|------|----------|
| [ADMIN_PANEL.md](./ADMIN_PANEL.md) | Полное руководство по админ-панели |
| [BROWSER_SETUP.md](./BROWSER_SETUP.md) | Настройка браузера и решение проблем |
| [CHATS_MANAGEMENT.md](./CHATS_MANAGEMENT.md) | Управление чатами уведомлений |
| [SERVER.md](./SERVER.md) | Руководство по развертыванию на сервере |
| [QUICKSTART.md](./QUICKSTART.md) | Быстрый старт за 5 минут |

## Советы и подводные камни

### 1. Селекторы DOM

Если сайт vitrina.gge.ru изменит HTML структуру, нужно обновить селекторы в:
- `src/browser/session.py` — селекторы формы входа
- `src/services/projects.py` — селекторы списка проектов

### 2. Авторизация

Сессия автоматически переавторизуется при 401 ошибке API. Учетные данные хранятся в БД.

### 3. Производительность

Для больших объемов проектов можно оптимизировать:
- Увеличить `limit` в `fetch_list()`
- Использовать параллельные запросы для деталей проектов

### 4. Обработка ошибок

Все ошибки записываются в лог и отправляются в Telegram как оповещение.

### 5. Админ-панель

- Настройки из `.env` используются только при первом запуске
- После первой настройки все изменения делаются через `/admin`
- Изменения в `.env` требуют перезапуска парсера

## Отладка

### Запуск с видимым браузером

```bash
HEADLESS=false RUN_ON_START=true python -m src.main
```

### Проверка БД

```bash
# Количество проектов
sqlite3 data/vitrina.db "SELECT COUNT(*) FROM projects;"

# Последние проекты
sqlite3 data/vitrina.db "SELECT object_name, region FROM projects ORDER BY created_at DESC LIMIT 5;"

# Настройки парсера
sqlite3 data/vitrina.db "SELECT key, value FROM parser_settings;"

# Список админов
sqlite3 data/vitrina.db "SELECT telegram_id FROM admins;"

# Чаты для уведомлений
sqlite3 data/vitrina.db "SELECT chat_id, is_active FROM notification_chats;"

# Учетные данные
sqlite3 data/vitrina.db "SELECT login, is_active FROM credentials;"
```

### Просмотр логов

```bash
tail -f logs/parser-$(date +%Y-%m-%d).log
```

### Тестирование авторизации

```bash
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

## Развертывание

### Docker

```bash
docker-compose up -d
docker-compose logs -f
```

### systemd (Linux)

```bash
sudo cp systemd/vitrina-parser.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start vitrina-parser
sudo systemctl enable vitrina-parser
```

Смотрите [SERVER.md](./SERVER.md) для подробной инструкции.

## Лицензия

MIT License

## Быстрый старт

1. **Установить зависимости:**
   ```bash
   pip install -r requirements.txt && playwright install chromium
   ```

2. **Настроить .env:**
   ```bash
   cp .env.example .env
   # Отредактировать: логин/пароль, токен бота, ADMIN_ID
   ```

3. **Запустить:**
   ```bash
   python -m src.main
   ```

4. **Настроить через Telegram:**
   - Отправить `/start`
   - Открыть `/admin` для настройки фильтров и расписания

## Поддержка

- 📚 [Админ-панель](./ADMIN_PANEL.md) — полное руководство по настройке
- 🔧 [Настройка браузера](./BROWSER_SETUP.md) — решение проблем с Playwright
- 📱 [Управление чатами](./CHATS_MANAGEMENT.md) — добавление чатов для уведомлений
- 🖥️ [Развертывание](./SERVER.md) — запуск на сервере (Docker, systemd)
- ⚡ [Быстрый старт](./QUICKSTART.md) — запуск за 5 минут

## Автор

Vitrina Parser — инструмент для мониторинга инвестиционных проектов.
