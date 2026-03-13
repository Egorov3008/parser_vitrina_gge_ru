# Парсер Витрина Проектов

Автоматизированный парсер портала [vitrina.gge.ru](https://vitrina.gge.ru) для ежедневного мониторинга новых инвестиционных проектов с уведомлениями в Telegram.

## Функциональность

- 🔍 **Парсинг проектов** — автоматическая выборка новых объектов по настраиваемым фильтрам
- 📋 **Фильтрация** — по категориям, регионам и дате публикации
- 📱 **Telegram уведомления** — информирование о новых проектах с полной информацией
- 📊 **Статистика** — отслеживание количества проектов и ошибок
- ⏱ **Гибкое расписание** — cron-выражения для запуска по расписанию
- 💾 **SQLite БД** — хранение информации о проектах и логах запусков

## Требования

- Python 3.11+
- Chromium браузер (для Playwright)

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
VITRINA_LOGIN=your_email@example.com
VITRINA_PASSWORD=your_password

# Telegram бот (создать через @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:AAExampleToken
TELEGRAM_CHAT_ID=-1001234567890  # ID чата (с минусом для групп)

# Фильтры (JSON массивы)
FILTER_CATEGORIES=["Жилые здания","Административные здания"]
FILTER_REGIONS=["Москва","Московская область"]
FILTER_DAYS_BACK=1

# Расписание (cron, UTC)
CRON_SCHEDULE=0 6 * * *  # 6:00 UTC каждый день

# Запуск при старте
RUN_ON_START=false
```

## Использование

### Запуск парсера

```bash
python -m src.main
```

Бот будет ждать команд в Telegram чате.

### Telegram команды

- **`/start`** — приветствие и список команд
- **`/status`** — информация о последнем запуске
- **`/run_now`** — запустить парсер немедленно
- **`/stats`** — статистика проектов и ошибок
- **`/help`** — справка по командам

### Примеры

**Проверить последний запуск:**
```bash
/status
```

**Принудительно запустить парсер:**
```bash
/run_now
```

**Просмотреть статистику:**
```bash
/stats
```

## Архитектура

```
src/
├── main.py              # Точка входа, Telegram бот
├── config.py            # Загрузка конфига из .env
│
├── browser/
│   ├── session.py       # Управление браузер-сессией (Playwright)
│   └── scraper.py       # Вспомогательные методы DOM парсинга
│
├── services/
│   ├── projects.py      # Парсинг списка и деталей проектов
│   ├── telegram.py      # Отправка уведомлений в Telegram
│   └── scheduler.py     # APScheduler и pipeline парсинга
│
├── db/
│   ├── database.py      # Управление SQLite подключением
│   └── repository.py    # Работа с данными проектов
│
└── utils/
    ├── logger.py        # Loguru настройка
    └── formatters.py    # Форматирование сообщений Telegram
```

## Технологический стек

| Компонент | Пакет | Версия |
|-----------|-------|--------|
| Браузер | `playwright` | >=1.40.0 |
| Telegram бот | `python-telegram-bot` | >=20.0 |
| Планировщик | `apscheduler` | >=3.10.4 |
| Конфиг | `python-dotenv`, `pydantic-settings` | >=1.0, >=2.0 |
| Логирование | `loguru` | >=0.7.2 |
| HTTP | `httpx` | >=0.25.0 |

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

## Логирование

Логи сохраняются в `logs/parser-YYYY-MM-DD.log` с ротацией по дням.

Уровни логирования настраиваются через `LOG_LEVEL` в `.env`:
- `DEBUG` — детальная информация
- `INFO` — основные события
- `WARNING` — предупреждения
- `ERROR` — ошибки
- `CRITICAL` — критические ошибки

## Советы и подводные камни

### 1. Селекторы DOM

Если сайт vitrina.gge.ru изменит HTML структуру, нужно обновить селекторы в:
- `src/browser/session.py` — селекторы формы входа
- `src/services/projects.py` — селекторы списка проектов

### 2. Авторизация

Сессия автоматически переавторизуется при 401 ошибке API.

### 3. Производительность

Для больших объемов проектов можно оптимизировать:
- Увеличить `limit` в `fetch_list()`
- Использовать параллельные запросы для деталей проектов

### 4. Обработка ошибок

Все ошибки записываются в лог и отправляются в Telegram как оповещение.

## Отладка

### Запуск с видимым браузером

```bash
HEADLESS=false RUN_ON_START=true python -m src.main
```

### Проверка БД

```bash
sqlite3 data/vitrina.db "SELECT COUNT(*) FROM projects;"
```

### Просмотр логов

```bash
tail -f logs/parser-$(date +%Y-%m-%d).log
```

## Лицензия

MIT License

## Автор

Vitrina Parser — инструмент для мониторинга инвестиционных проектов.
