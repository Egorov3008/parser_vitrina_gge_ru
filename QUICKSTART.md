# Быстрый старт

Запуск парсера Vitrina за 5-10 минут.

## Вариант 1: Локальный запуск (рекомендуется для тестирования)

### 1. Установка зависимостей (2-3 минуты)

```bash
cd /home/claude/vitrina-parser

# Создать виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate

# Установить Python зависимости
pip install -r requirements.txt

# Установить Chromium
playwright install chromium
```

**Linux:** Установить системные зависимости браузера:
```bash
chmod +x install_browser_deps.sh
sudo bash install_browser_deps.sh
```

### 2. Настройка конфигурации (2 минуты)

```bash
# Скопировать шаблон
cp .env.example .env

# Отредактировать
nano .env
```

**Минимальная конфигурация:**

```env
# Портал vitrina.gge.ru
VITRINA_LOGIN=your_email@example.com
VITRINA_PASSWORD=your_password

# Telegram бот
TELEGRAM_BOT_TOKEN=1234567890:AAExampleToken
TELEGRAM_CHAT_ID=-1001234567890

# Администратор (вы)
ADMIN_ID=123456789
```

**Как получить данные:**

| Данные | Где получить | Время |
|--------|--------------|-------|
| `VITRINA_LOGIN` | Личный кабинет на vitrina.gge.ru | 1 мин |
| `VITRINA_PASSWORD` | Личный кабинет на vitrina.gge.ru | - |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/botfather) | 2 мин |
| `TELEGRAM_CHAT_ID` | [@userinfobot](https://t.me/userinfobot) | 30 сек |
| `ADMIN_ID` | [@userinfobot](https://t.me/userinfobot) | 30 сек |

**Пошаговая инструкция для Telegram:**

1. **Создать бота:**
   - Открыть [@BotFather](https://t.me/botfather)
   - Отправить `/newbot`
   - Ввести имя бота (например, "Vitrina Parser")
   - Ввести username бота (например, "vitrina_parser_bot")
   - Скопировать токен (выглядит как `1234567890:AAExampleToken`)

2. **Получить ID чата:**
   - Открыть [@userinfobot](https://t.me/userinfobot)
   - Нажать "Start"
   - Скопировать ID (например, `123456789`)

3. **Добавить бота в чат (опционально):**
   - Создать группу/канал
   - Добавить бота
   - Отправить `/getChatId` для получения ID группы

### 3. Первый запуск (1 минута)

```bash
# Запустить с немедленной проверкой
RUN_ON_START=true HEADLESS=false python -m src.main
```

**Флаги:**
- `RUN_ON_START=true` — запустить парсер сразу при старте
- `HEADLESS=false` — показать браузер (видно процесс авторизации)

**Что происходит:**
1. Запускается браузер
2. Происходит авторизация на vitrina.gge.ru
3. Парсер получает список проектов
4. Отправляет уведомления в Telegram
5. Бот переходит в режим ожидания команд

### 4. Проверка результатов

**В Telegram:**
- Бот отправит приветственное сообщение
- При нахождении проектов — уведомления с деталями

**В логах:**
```bash
tail -f logs/parser-*.log
```

**В базе данных:**
```bash
sqlite3 data/vitrina.db "SELECT COUNT(*) FROM projects;"
sqlite3 data/vitrina.db "SELECT object_name, region FROM projects LIMIT 5;"
```

---

## Вариант 2: Docker (для продакшена)

### 1. Установка Docker (5 минут)

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Проверка
docker --version
docker-compose --version
```

### 2. Настройка (2 минуты)

```bash
# Клонировать репозиторий
git clone <repository-url>
cd vitrina-parser

# Настроить .env
cp .env.example .env
nano .env
```

### 3. Запуск (1 минута)

```bash
docker-compose up -d
```

**Проверка:**
```bash
docker-compose ps
docker-compose logs -f
```

---

## Вариант 3: systemd (для Linux серверов)

### 1. Установка (5 минут)

```bash
# Клонировать репозиторий
cd /opt
git clone <repository-url> vitrina-parser
cd vitrina-parser

# Создать venv
python3.11 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
playwright install chromium

# Системные зависимости
sudo bash install_browser_deps.sh
```

### 2. Настройка сервиса (2 минуты)

```bash
# Скопировать сервис
sudo cp systemd/vitrina-parser.service /etc/systemd/system/

# Включить и запустить
sudo systemctl daemon-reload
sudo systemctl enable vitrina-parser
sudo systemctl start vitrina-parser
```

### 3. Проверка

```bash
sudo systemctl status vitrina-parser
journalctl -u vitrina-parser -f
```

---

## Настройка через Telegram

После первого запуска настройте фильтры через админ-панель:

### 1. Открыть админ-панель

Отправить боту:
```
/admin
```

### 2. Настроить фильтры

**Категории:**
- Нажать "📁 Категории"
- Выбрать нужные (например, "Жилые объекты")
- Нажать "✅ Готово"

**Регионы:**
- Нажать "📍 Регионы"
- Выбрать нужные (например, "Москва", "Московская область")
- Нажать "✅ Готово"

**Расписание:**
- Нажать "⏰ Расписание"
- Выбрать готовый пресет или настроить вручную
- Например: "Ежедневно в 06:00"

**Чаты:**
- Нажать "📱 Чаты"
- Отправить ID чата (получить через `/getChatId`)
- Чат добавлен

---

## Типичные проблемы и решения

### ❌ Ошибка авторизации

**Симптом:**
```
Login failed - still on login page
```

**Решение:**
1. Проверить логин/пароль в `.env`
2. Попробовать войти на vitrina.gge.ru вручную
3. Запустить с `HEADLESS=false` для отладки
4. Проверить селекторы в `src/browser/session.py`

---

### ❌ Ошибка браузера

**Симптом:**
```
chrome-headless-shell: error while loading shared libraries: libnspr4.so
```

**Решение:**
```bash
# Установить зависимости
sudo bash install_browser_deps.sh

# Или вручную
sudo apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0

# Переустановить Chromium
playwright install chromium
```

---

### ❌ Бот не отвечает

**Симптом:** Команды в Telegram не работают

**Решение:**
1. Проверить токен в `.env`
2. Проверить логи: `tail -f logs/parser-*.log`
3. Перезапустить бота
4. Убедиться, что бот добавлен в чат (если группа)

---

### ❌ Telegram не получает уведомления

**Симптом:** Парсер работает, но уведомлений нет

**Решение:**
1. Проверить `TELEGRAM_CHAT_ID` в `.env`
2. Проверить, что бот добавлен в чат
3. Проверить логи на ошибки отправки
4. Использовать `/getChatId` для получения правильного ID

---

### ❌ Ошибка БД

**Симптом:**
```
No such table: projects
```

**Решение:**
```bash
# Удалить старую БД (внимание: все данные будут потеряны!)
rm data/vitrina.db

# БД будет создана автоматически
python -m src.main
```

---

## Полезные команды

### Управление ботом

```bash
# Запустить
python -m src.main

# Запустить с отладкой
RUN_ON_START=true HEADLESS=false python -m src.main

# Остановить (Ctrl+C)
```

### Проверка данных

```bash
# Количество проектов
sqlite3 data/vitrina.db "SELECT COUNT(*) FROM projects;"

# Последние проекты
sqlite3 data/vitrina.db "SELECT object_name, region, published_at FROM projects ORDER BY created_at DESC LIMIT 10;"

# Статистика по категориям
sqlite3 data/vitrina.db "SELECT category, COUNT(*) as count FROM projects GROUP BY category;"

# Настройки парсера
sqlite3 data/vitrina.db "SELECT key, value FROM parser_settings;"
```

### Логи

```bash
# Просмотр в реальном времени
tail -f logs/parser-$(date +%Y-%m-%d).log

# Поиск ошибок
grep "ERROR" logs/parser-*.log

# Последние 50 строк
tail -n 50 logs/parser-*.log
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

---

## Следующие шаги

После успешного запуска:

1. **Настроить фильтры** через `/admin`
   - Категории проектов
   - Регионы
   - Расписание

2. **Добавить чаты** для уведомлений
   - Личный чат
   - Рабочая группа
   - Канал

3. **Настроить мониторинг**
   - Проверять логи регулярно
   - Настроить уведомления об ошибках

4. **Автоматизировать запуск**
   - Docker для продакшена
   - systemd для Linux
   - Cron для периодического запуска

5. **Резервное копирование**
   - Бэкап БД: `cp data/vitrina.db backup/`
   - Бэкап `.env` файла

---

## Чек-лист успешной установки

- [ ] Python 3.11+ установлен
- [ ] Виртуальное окружение создано
- [ ] Зависимости установлены (`pip install -r requirements.txt`)
- [ ] Chromium установлен (`playwright install chromium`)
- [ ] Системные зависимости установлены
- [ ] `.env` файл настроен
- [ ] Бот запускается без ошибок
- [ ] Telegram бот отвечает на `/start`
- [ ] Парсер находит проекты
- [ ] Уведомления приходят в Telegram
- [ ] Админ-панель доступна (`/admin`)

---

## Ресурсы

- [Полная документация](./README.md)
- [Админ-панель](./ADMIN_PANEL.md)
- [Настройка браузера](./BROWSER_SETUP.md)
- [Развертывание на сервере](./SERVER.md)
- [Управление чатами](./CHATS_MANAGEMENT.md)

---

## Поддержка

При возникновении проблем:

1. Проверьте логи: `tail -f logs/parser-*.log`
2. Поищите в документации нужную секцию
3. Проверьте типичные проблемы выше
4. Откройте issue в репозитории

Удачи! 🚀
