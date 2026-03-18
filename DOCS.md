# Документация Vitrina Parser

Добро пожаловать в документацию парсера инвестиционных проектов портала vitrina.gge.ru.

## 📚 Все документы

### Основная документация

| Документ | Описание | Для кого |
|----------|----------|----------|
| [README.md](./README.md) | Основная документация проекта | Все пользователи |
| [QUICKSTART.md](./QUICKSTART.md) | Быстрый старт за 5 минут | Новые пользователи |
| [ADMIN_PANEL.md](./ADMIN_PANEL.md) | Руководство по админ-панели | Администраторы |

### Технические руководства

| Документ | Описание | Для кого |
|----------|----------|----------|
| [SERVER.md](./SERVER.md) | Развертывание на сервере | DevOps, сисадмины |
| [BROWSER_SETUP.md](./BROWSER_SETUP.md) | Настройка браузера Playwright | Все пользователи |
| [CHATS_MANAGEMENT.md](./CHATS_MANAGEMENT.md) | Управление чатами уведомлений | Администраторы |

### Отладка и решение проблем

| Документ | Описание | Для кого |
|----------|----------|----------|
| [BUGFIX_NET_ERR_ABORTED.md](./BUGFIX_NET_ERR_ABORTED.md) | Исправление ошибки NET::ERR_ABORTED | Разработчики |
| [TESTING_LOGGING.md](./TESTING_LOGGING.md) | Тестирование и логирование | Разработчики |
| [SYSTEM_ANALYSIS.md](./SYSTEM_ANALYSIS.md) | Анализ системы | Разработчики |

### Архив/История

| Документ | Описание |
|----------|----------|
| [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) | История реализации |
| [PLAN_IMPLEMENTATION_SUMMARY.md](./PLAN_IMPLEMENTATION_SUMMARY.md) | План реализации |
| [TEST_IMPLEMENTATION.md](./TEST_IMPLEMENTATION.md) | Тестирование |
| [CLAUDE.md](./CLAUDE.md) | Контекст для Claude |
| [QWEN.md](./QWEN.md) | Контекст для Qwen |

---

## 🚀 Быстрый старт

### За 5 минут

1. **Установить зависимости:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Настроить .env:**
   ```bash
   cp .env.example .env
   nano .env
   ```

3. **Запустить:**
   ```bash
   python -m src.main
   ```

**Подробно:** [QUICKSTART.md](./QUICKSTART.md)

---

## 📖 Руководства

### Для новых пользователей

1. Начните с [QUICKSTART.md](./QUICKSTART.md)
2. Прочитайте [README.md](./README.md)
3. Настройте админ-панель через [ADMIN_PANEL.md](./ADMIN_PANEL.md)

### Для администраторов

1. Изучите [ADMIN_PANEL.md](./ADMIN_PANEL.md)
2. Настройте чаты через [CHATS_MANAGEMENT.md](./CHATS_MANAGEMENT.md)
3. Настройте мониторинг и логи

### Для разработчиков

1. Изучите архитектуру в [README.md](./README.md)
2. Проверьте [SYSTEM_ANALYSIS.md](./SYSTEM_ANALYSIS.md)
3. Используйте [TESTING_LOGGING.md](./TESTING_LOGGING.md) для отладки

### Для DevOps

1. Выберите способ развертывания в [SERVER.md](./SERVER.md)
2. Настройте мониторинг и логирование
3. Настройте резервное копирование

---

## 🎯 Популярные задачи

### Настройка фильтров

```
/admin → Категории → Выбрать нужные
/admin → Регионы → Выбрать нужные
/admin → Расписание → Настроить время
```

**Подробно:** [ADMIN_PANEL.md](./ADMIN_PANEL.md)

### Добавление чатов

1. Отправить `/getChatId` в чат
2. `/admin` → Чаты → Отправить ID
3. Готово ✅

**Подробно:** [CHATS_MANAGEMENT.md](./CHATS_MANAGEMENT.md)

### Решение проблем с браузером

```bash
sudo bash install_browser_deps.sh
playwright install chromium
```

**Подробно:** [BROWSER_SETUP.md](./BROWSER_SETUP.md)

### Развертывание на сервере

**Docker:**
```bash
docker-compose up -d
```

**systemd:**
```bash
sudo systemctl enable vitrina-parser
sudo systemctl start vitrina-parser
```

**Подробно:** [SERVER.md](./SERVER.md)

---

## 📋 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/status` | Статус последнего запуска |
| `/run_now` | Запустить парсер |
| `/stop` | Остановить парсер |
| `/stats` | Статистика проектов |
| `/admin` | Админ-панель |
| `/add_admin` | Добавить администратора |
| `/getChatId` | Получить ID чата |
| `/help` | Справка |

---

## 🔧 Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `VITRINA_LOGIN` | Логин для портала | - |
| `VITRINA_PASSWORD` | Пароль для портала | - |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | - |
| `ADMIN_ID` | ID администраторов | - |
| `CRON_SCHEDULE` | Расписание (cron) | `0 6 * * *` |
| `RUN_ON_START` | Запуск при старте | `false` |
| `HEADLESS` | Режим браузера | `true` |
| `LOG_LEVEL` | Уровень логов | `INFO` |

**Пример:** [.env.example](./.env.example)

---

## 🗂️ Структура проекта

```
vitrina-parser/
├── src/
│   ├── main.py              # Точка входа
│   ├── config.py            # Конфигурация
│   ├── browser/             # Browser automation
│   ├── services/            # Business logic
│   ├── db/                  # Database
│   └── utils/               # Helpers
├── data/                    # SQLite database
├── logs/                    # Log files
├── docs/                    # Documentation
├── systemd/                 # systemd service
├── docker-compose.yml       # Docker
├── requirements.txt         # Dependencies
└── .env.example             # Config template
```

---

## 🆘 Решение проблем

### Частые ошибки

| Ошибка | Решение |
|--------|---------|
| `libnspr4.so: cannot open` | [BROWSER_SETUP.md](./BROWSER_SETUP.md) |
| `Login failed` | Проверить логин/пароль, запустить с `HEADLESS=false` |
| Бот не отвечает | Проверить токен, перезапустить |
| Нет уведомлений | Проверить чаты в `/admin`, проверить права бота |

### Логи

```bash
# Сегодняшние логи
tail -f logs/parser-$(date +%Y-%m-%d).log

# Поиск ошибок
grep "ERROR" logs/parser-*.log
```

---

## 📞 Поддержка

### Документация

- 📚 [README.md](./README.md) — основная документация
- ⚡ [QUICKSTART.md](./QUICKSTART.md) — быстрый старт
- ⚙️ [ADMIN_PANEL.md](./ADMIN_PANEL.md) — админ-панель
- 🖥️ [SERVER.md](./SERVER.md) — развертывание
- 🔧 [BROWSER_SETUP.md](./BROWSER_SETUP.md) — браузер
- 📱 [CHATS_MANAGEMENT.md](./CHATS_MANAGEMENT.md) — чаты

### Ресурсы

- Портал: [vitrina.gge.ru](https://vitrina.gge.ru)
- Telegram Bot API: [core.telegram.org/bots](https://core.telegram.org/bots)
- Playwright: [playwright.dev](https://playwright.dev)

---

## 📝 История версий

Смотрите релизы в репозитории.

---

## 📄 Лицензия

MIT License
