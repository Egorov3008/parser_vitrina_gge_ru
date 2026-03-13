# Тестирование реализации фильтров

## Что было изменено

### 1. `src/services/projects.py`
- ✅ Добавлены параметры `year_from` и `year_to` к методу `fetch_list()`
- ✅ Реализован новый метод `_fetch_via_browser_search()` с перехватом AJAX ответа
- ✅ Реализован метод `_set_slimselect_filter()` для установки фильтров категорий и регионов
- ✅ Реализован метод `_set_expertise_year_input()` для заполнения поля года
- ✅ Реализован метод `_submit_search_form()` для отправки формы поиска
- ✅ Реализован метод `_fetch_with_year_range()` для обработки диапазона лет

### 2. `src/services/scheduler.py`
- ✅ Обновлен вызов `fetch_list()` для передачи параметров `year_from` и `year_to`
- ✅ Удален вызов `filter_by_expertise_year()` (фильтрация теперь на стороне сервера)

### 3. `src/services/admin_panel.py`
- ✅ Обновлен список `ALL_REGIONS` с полным списком 85 федеральных субъектов РФ
- ✅ Добавлены коды регионов (77 - Москва, 78 - СПб и т.д.)

## Как работает новая логика

1. **При установке фильтров в админ-панели:**
   - Пользователь выбирает категории, регионы и диапазон лет
   - Настройки сохраняются в БД

2. **При запуске парсера:**
   - Загружаются настройки из БД
   - Вызывается `fetch_list()` с параметрами категорий, регионов, года
   - Если задан год (year_from или year_to):
     - Используется браузерный поиск `_fetch_via_browser_search()`
     - Если нужен диапазон лет - вызывается каждый год отдельно
     - Результаты объединяются и дедублируются
   - Иначе:
     - Попытка API запроса
     - Fallback на браузерный поиск без года

3. **При браузерном поиске:**
   - Перехватывается ответ от `/projects/search` API
   - Используется реальный JSON ответ от сервера
   - Это гарантирует использование правильного формата параметров фильтров

## Проверка (верификация)

### Вариант 1: Через админ-панель и Telegram

```bash
# 1. Запустить парсер
python -m src.main

# 2. В Telegram боте отправить /admin
# 3. Установить фильтры:
#    - Категория: "Образование"
#    - Регион: "г. Москва" (или "77. г. Москва")
#    - Год: от 2023 до 2024

# 4. Отправить /run_now

# 5. Проверить логи:
tail -f logs/parser-$(date +%Y-%m-%d).log
```

Ожидаемый результат в логах:
```
Starting parser run
Last run: ...
Expertise year filter: 2023 - 2024
Category filter: ['Образование']
Region filter: ['г. Москва']
Fetching projects via browser search
Setting Категория filter: ['Образование']
Setting Регион filter: ['г. Москва']
Setting expertise year: 2023
Submitting search form
Fetched X projects via search API
```

### Вариант 2: Через Python скрипт (для разработки)

```python
import asyncio
from src.browser.session import SessionManager
from src.services.projects import ProjectsService

async def test():
    session = SessionManager()
    await session.initialize()

    service = ProjectsService(session)
    await service.initialize()

    # Тест 1: Фильтр по году
    projects = await service.fetch_list(
        year_from=2023,
        year_to=2024,
    )
    print(f"Projects with year filter: {len(projects)}")

    # Тест 2: Фильтр по году и категории
    projects = await service.fetch_list(
        categories=["Образование"],
        regions=["Москва"],
        year_from=2023,
        year_to=2023,
    )
    print(f"Projects with all filters: {len(projects)}")

    await service.close()
    await session.close()

asyncio.run(test())
```

### Вариант 3: Проверка логов (в продакшене)

Основные метрики для проверки:
1. **При фильтре по году** - в логах должно появиться несколько запросов (один на каждый год)
2. **Количество проектов** - должно быть меньше, чем без фильтров
3. **Отсутствие ошибок** - не должно быть ошибок при установке фильтров

## Потенциальные проблемы и решения

### Проблема 1: Фильтры не применяются
**Причина:** Возможно изменилась структура HTML на сайте или названия placeholder'ов.

**Решение:**
1. Проверить живой сайт: откройте https://vitrina.gge.ru/projects/ в браузере
2. Нажмите F12, откройте DevTools
3. Найдите элемент `.ss-main` (SlimSelect дропдаун)
4. Проверьте точное текстовое содержимое
5. Обновите названия фильтров в методе `_set_slimselect_filter()`

### Проблема 2: Форма поиска не отправляется
**Причина:** Кнопка поиска может иметь другой селектор.

**Решение:**
1. Проверьте в DevTools какой селектор у кнопки "Поиск"
2. Добавьте селектор в метод `_submit_search_form()`

### Проблема 3: Поле года не заполняется
**Причина:** Поле может называться по-другому или находиться в другом месте.

**Решение:**
1. Найдите поле в DevTools
2. Проверьте его name, id, placeholder
3. Обновите селекторы в методе `_set_expertise_year_input()`

### Проблема 4: Timeout при ожидании ответа
**Причина:** Форма отправляется, но AJAX ответ не перехватывается.

**Решение:**
1. Убедитесь, что endpoint действительно `/projects/search`
2. Проверьте в Network tab браузера точный URL запроса
3. Может потребоваться обновить URL в методе `capture_response()`

## Логирование для отладки

При возникновении проблем можно включить дополнительное логирование:

```python
# В методе _fetch_via_browser_search добавить перед capture_response:

async def capture_response(response):
    print(f"Response: {response.url} - {response.status}")  # DEBUG
    # ... остальной код
```

Это поможет увидеть все получаемые ответы и найти нужный запрос.

## Откат изменений (если необходимо)

Если новая логика вызывает проблемы, можно временно отключить браузерный поиск и вернуться к старому методу:

```python
# В fetch_list(), закомментировать строку:
# if year_from or year_to:
#     return await self._fetch_with_year_range(...)
```

При этом фильтрация по году будет работать по-старому (после получения всех проектов).
