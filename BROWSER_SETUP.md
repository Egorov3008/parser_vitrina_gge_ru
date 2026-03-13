# Установка системных зависимостей для Playwright Chromium

## Проблема

При запуске парсера возникает ошибка:

```
chrome-headless-shell: error while loading shared libraries: libnspr4.so: cannot open shared object file: No such file or directory
```

Это означает, что в системе отсутствуют библиотеки, необходимые для работы Chromium браузера.

## Решение

### Вариант 1: Автоматическая установка (РЕКОМЕНДУЕТСЯ)

#### Шаг 1: Сделайте скрипт исполняемым
```bash
chmod +x install_browser_deps.sh
```

#### Шаг 2: Запустите скрипт с правами администратора
```bash
sudo bash install_browser_deps.sh
```

Скрипт автоматически установит все необходимые библиотеки.

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
    libxss1
```

---

### Вариант 3: Через Playwright install-deps (требует интерактивный терминал)

Если вы находитесь в интерактивном окружении:

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Установите зависимости через Playwright
playwright install-deps chromium
```

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
- **libnspr4** (NSPR - Netscape Portable Runtime) - основная библиотека для браузера
- **libnss3** (NSS - Network Security Services) - криптография и SSL/TLS
- **libatk1.0-0** - библиотека доступности
- **libatk-bridge2.0-0** - мост для доступности
- **libcups2** - поддержка печати
- **libgbm1** - управление буферами GPU

### Графические и оконные библиотеки
- **libx11-6, libx11-xcb1, libxcb1** - X Window System
- **libxfixes3, libxdamage1, libxcomposite1** - расширения X11
- **libxrandr2** - управление разрешением экрана
- **libxkbcommon0** - управление клавиатурой
- **libgtk-3-0** - GTK библиотека
- **libcairo2** - граница рисования
- **libpango-1.0-0** - текстовая раскладка

### Остальные
- **libasound2** - поддержка звука
- **libxshmfence1** - синхронизация X11
- **libxss1** - расширение скринсейвера

---

## Troubleshooting

### Проблема: "sudo: a terminal is required"
**Решение:** Это нормально в неинтерактивных окружениях. Используйте Вариант 1 или 2 выше.

### Проблема: "E: Unable to locate package"
**Решение:** Сначала запустите `sudo apt-get update` для обновления кэша пакетов.

### Проблема: Ошибка всё ещё возникает
**Решение:** Проверьте:
1. Что вы используете правильную версию Python (3.11+)
2. Что виртуальное окружение активировано
3. Что выполнены все команды установки
4. Попробуйте переустановить Playwright:
   ```bash
   pip uninstall -y playwright
   pip install playwright
   playwright install chromium
   ```

---

## Дополнительная информация

Для более подробной информации о требованиях Playwright смотрите:
https://playwright.dev/python/docs/intro

Для информации о VPN Web Service смотрите: [MEMORY.md](/home/claude/.claude/projects/-home-claude/memory/MEMORY.md)
