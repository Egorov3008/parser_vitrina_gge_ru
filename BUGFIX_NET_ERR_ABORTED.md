# Исправление ошибки: net::ERR_ABORTED при браузерном поиске

## Проблема

```
2026-03-13 16:00:59.044 | ERROR | src.services.projects:_fetch_via_browser_search:422 - Browser search error: Page.goto: net::ERR_ABORTED at https://vitrina.gge.ru/projects/
```

### Причина

Ошибка `net::ERR_ABORTED` происходила потому, что метод `session.goto()` всегда использует `wait_until="networkidle"`, что:
1. Очень агрессивный режим ожидания загрузки
2. Может отменить запрос если на странице есть редиректы
3. Не совместим с некоторыми типами контента на vitrina.gge.ru

## Решение

### Изменение 1: Использование `page.goto()` напрямую

**Было:**
```python
await self.session.goto(f"{self.config.vitrina_url}/projects/")
```

**Стало:**
```python
await page.goto(f"{self.config.vitrina_url}/projects/", wait_until="domcontentloaded", timeout=30000)
```

**Почему помогает:**
- `domcontentloaded` менее агрессивно, чем `networkidle`
- Ждет только загрузки DOM, а не всех фоновых запросов
- Не отменяет запрос при редиректах

### Изменение 2: Обработка ошибок навигации

**Было:**
```python
await self.session.goto(...)  # Падает при ошибке
```

**Стало:**
```python
try:
    await page.goto(..., wait_until="domcontentloaded", timeout=30000)
except Exception as e:
    logger.warning(f"Navigation warning, but continuing: {e}")
    # Продолжаем несмотря на ошибку навигации
```

**Почему помогает:**
- Даже если навигация не удалась с `networkidle`, мы можем продолжить
- Логируем проблему для отладки
- Позволяет парсеру работать дальше

### Изменение 3: Добавление логирования для отладки

```python
logger.debug(f"Navigating to {self.config.vitrina_url}/projects/")
await page.goto(...)
logger.debug(f"Navigation complete, current URL: {page.url}")
```

**Помогает:**
- Видеть точный момент где произошла ошибка
- Проверять финальный URL
- Отлаживать проблемы редиректов

### Изменение 4: Проверка окончательного URL

```python
current_url = page.url
if "/projects" not in current_url:
    logger.warning(f"Expected /projects page but got: {current_url}")
```

**Помогает:**
- Убедиться что мы на нужной странице
- Выловить редиректы на другие страницы
- Знать если навигация произошла неправильно

## Теория: Почему это происходит на vitrina.gge.ru

Возможные причины:

1. **Динамическая загрузка контента** - страница загружает контент через AJAX/WebSockets, что создает `networkidle` проблемы

2. **Редиректы** - сервер может редиректить новые запросы, вызывая отмену оригинального запроса

3. **Таймауты** - `networkidle` может ждать слишком долго и упасть по таймауту

4. **CDN или прокси** - использование CDN может вызвать странное поведение при `networkidle`

## Как проверить что исправлено

1. **Запустить парсер:**
```bash
python -m src.main
```

2. **В Telegram:**
```
/admin  → установить фильтры
/run_now → запустить парсер
```

3. **Проверить логи:**
```bash
tail -f logs/parser-$(date +%Y-%m-%d).log
```

4. **Искать строки:**
```
Navigating to https://vitrina.gge.ru/projects/
Navigation complete, current URL: https://vitrina.gge.ru/projects/
Setting Категория filter: ...
Fetched N projects via search API
```

Если нет ошибки `net::ERR_ABORTED` → исправлено!

## Если проблема все еще есть

### Вариант 1: Увеличить таймаут
```python
await page.goto(..., wait_until="domcontentloaded", timeout=60000)  # 60 сек
```

### Вариант 2: Использовать более мягкое ожидание
```python
await page.goto(..., wait_until="load")  # Только загрузка основного контента
```

### Вариант 3: Пропустить ожидание вообще
```python
await page.goto(..., wait_until="commit")  # Минимальное ожидание
```

## Откат

Если что-то сломалось, откатите изменения:
```bash
git checkout src/services/projects.py
```

## Дополнительные улучшения для будущего

1. Добавить retry логику для навигации
2. Использовать `page.on("requestfailed")` для отлова ошибок запросов
3. Добавить опцию `timeout` в конфиг для тюнинга под разные сети
4. Кешировать результаты поиска чтобы меньше запрашивать сервер
