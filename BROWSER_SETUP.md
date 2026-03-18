# Установка системных зависимостей для Playwright Chromium

## Проблема

При запуске парсера возникает ошибка:

```
chrome-headless-shell: error while loading shared libraries: libnspr4.so: cannot open shared object file: No such file or directory
```

Или другие подобные ошибки с библиотеками:
- `libnss3.so`
- `libatk-bridge2.0-0.so`
- `libgbm1.so`
- `libxkbcommon0.so`

Это означает, что в системе отсутствуют библиотеки, необходимые для работы Chromium браузера.

---

## Решение

### Вариант 1: Автоматическая установка (РЕКОМЕНДУЕТСЯ) ⭐

#### Шаг 1: Сделайте скрипт исполняемым
```bash
chmod +x install_browser_deps.sh
```

#### Шаг 2: Запустите скрипт с правами администратора
```bash
sudo bash install_browser_deps.sh
```

Скрипт автоматически установит все необходимые библиотеки.

**Что делает скрипт:**
- Обновляет кэш пакетов `apt`
- Устанавливает все зависимости для Chromium
- Проверяет успешность установки

---

### Вариант 2: Ручная установка через apt-get

Если вы предпочитаете устанавливать вручную или скрипт не работает:

```bash
sudo apt-get update

sudo apt-get install -y \
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    libxshmfence1 \
    libxss1 \
    libgtk-3-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1
```

---

### Вариант 3: Через Playwright install-deps

Если вы находитесь в интерактивном окружении с правами root:

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Установите зависимости через Playwright
playwright install-deps chromium
```

**Примечание:** Эта команда может требовать интерактивный терминал и не работать в автоматическом режиме.

---

## Проверка установки

После установки системных зависимостей проверьте, что браузер работает:

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Проверьте, что Playwright Chromium установлен
playwright install chromium

# Попробуйте запустить парсер
python -m src.main
```

Если ошибка исчезла — всё готово!

---

## Что устанавливается?

### Основные библиотеки

| Библиотека | Описание |
|------------|----------|
| **libnspr4** | NSPR - Netscape Portable Runtime (основная библиотека) |
| **libnss3** | NSS - Network Security Services (SSL/TLS, криптография) |
| **libatk1.0-0** | Accessibility Toolkit (доступность) |
| **libatk-bridge2.0-0** | AT-SPI bridge (мост доступности) |
| **libcups2** | CUPS (поддержка печати) |
| **libgbm1** | Generic Buffer Management (GPU буферы) |

### Графические и оконные библиотеки

| Библиотека | Описание |
|------------|----------|
| **libx11-6, libx11-xcb1, libxcb1** | X Window System (оконная система) |
| **libxfixes3, libxdamage1, libxcomposite1** | X11 extensions (расширения) |
| **libxrandr2** | X Resize and Rotate (разрешение экрана) |
| **libxkbcommon0** | X Keyboard (клавиатура) |
| **libgtk-3-0** | GTK 3 (графический интерфейс) |
| **libcairo2** | Cairo graphics (2D графика) |
| **libpango-1.0-0** | Pango text layout (текст) |

### Остальные

| Библиотека | Описание |
|------------|----------|
| **libasound2** | ALSA sound (звук) |
| **libxshmfence1** | X11 sync (синхронизация) |
| **libxss1** | X Screen Saver (скринсейвер) |

---

## Платформы

### Ubuntu/Debian

```bash
# Автоматическая установка
sudo bash install_browser_deps.sh

# Или вручную
sudo apt-get update
sudo apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0
```

### CentOS/RHEL/Fedora

```bash
# Fedora
sudo dnf install -y nss nspr libX11 libXcomposite libXdamage libXrandr \
    libgbm libxkbcommon libXss libgtk3

# CentOS/RHEL
sudo yum install -y nss nspr libX11 libXcomposite libXdamage libXrandr \
    libgbm libxkbcommon libXss gtk3
```

### macOS

```bash
# Playwright автоматически устанавливает зависимости на macOS
playwright install chromium

# Если проблемы, попробуйте переустановить
pip uninstall -y playwright
pip install playwright
playwright install chromium
```

### Windows

```bash
# На Windows зависимости устанавливаются автоматически
playwright install chromium

# Если проблемы, запустите от имени администратора
```

### Docker

```dockerfile
# В Dockerfile добавьте
RUN playwright install-deps chromium
RUN playwright install chromium
```

Или используйте готовый образ:
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy
```

---

## Troubleshooting

### Проблема: "sudo: a terminal is required"

**Решение:** Это нормально в неинтерактивных окружениях (Docker, CI/CD).

**Варианты:**
1. Используйте Вариант 2 (ручная установка через apt-get)
2. В Docker используйте `install-deps`
3. В CI/CD настройте права sudo

---

### Проблема: "E: Unable to locate package"

**Решение:**
```bash
# Обновите кэш пакетов
sudo apt-get update

# Если не помогло, проверьте репозитории
sudo apt-get update --fix-missing

# Попробуйте снова
sudo apt-get install -y libnspr4 libnss3
```

---

### Проблема: Ошибка всё ещё возникает

**Проверьте:**

1. **Версия Python:**
   ```bash
   python3 --version
   # Должна быть 3.11+
   ```

2. **Виртуальное окружение активировано:**
   ```bash
   which python
   # Должен показывать путь внутри venv
   ```

3. **Playwright установлен:**
   ```bash
   pip list | grep playwright
   ```

4. **Chromium установлен:**
   ```bash
   playwright install chromium
   ```

**Полная переустановка:**
```bash
# Деактивировать venv
deactivate

# Удалить venv
rm -rf venv

# Создать новый
python3.11 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Переустановить Chromium
playwright install chromium

# Установить системные зависимости
sudo bash install_browser_deps.sh

# Запустить парсер
python -m src.main
```

---

### Проблема: "Failed to initialize browser"

**Причины:**
- Неполная установка Chromium
- Проблемы с правами доступа
- Конфликт версий

**Решение:**
```bash
# Очистить кэш Playwright
rm -rf ~/.cache/ms-playwright

# Переустановить Chromium
playwright install chromium

# Проверить права
ls -la ~/.cache/ms-playwright

# Запустить с правами (только для тестирования!)
sudo python -m src.main
```

---

### Проблема: Браузер запускается, но не работает авторизация

**Причины:**
- Сайт изменил HTML структуру
- Неправильные селекторы
- Блокировка по IP

**Решение:**
1. Запустить с видимым браузером:
   ```bash
   HEADLESS=false python -m src.main
   ```

2. Проверить логи:
   ```bash
   tail -f logs/parser-*.log
   ```

3. Обновить селекторы в `src/browser/session.py`

---

## Проверка работы браузера

### Тестовый скрипт

Создайте файл `test_browser.py`:

```python
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://vitrina.gge.ru")
        print(f"Status: {page.title()}")
        await browser.close()
    print("✅ Browser test passed!")

asyncio.run(test())
```

Запустите:
```bash
source venv/bin/activate
python test_browser.py
```

### Тест авторизации

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

## Дополнительная информация

### Ссылки

- [Playwright Documentation](https://playwright.dev/python/docs/intro)
- [Playwright Browsers](https://playwright.dev/python/docs/browsers)
- [Chromium Dependencies](https://github.com/microsoft/playwright/blob/main/docs/browsers.md)

### Логи

При проблемах проверяйте логи:
```bash
# Логи парсера
tail -f logs/parser-*.log

# Playwright debug
DEBUG=pw:api python -m src.main
```

### Системные требования

| Ресурс | Минимум | Рекомендуется |
|--------|---------|---------------|
| RAM | 512 MB | 1 GB |
| CPU | 1 core | 2 cores |
| Disk | 200 MB | 500 MB |

---

## См. также

- [QUICKSTART.md](./QUICKSTART.md) — быстрый старт
- [README.md](./README.md) — основная документация
- [SERVER.md](./SERVER.md) — развертывание на сервере
