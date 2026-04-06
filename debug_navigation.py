"""
Скрипт для диагностики навигации на страницу /projects
Запуск: HEADLESS=false python debug_navigation.py
"""
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os

load_dotenv()

VITRINA_URL = os.getenv("VITRINA_URL", "https://vitrina.gge.ru")
LOGIN = os.getenv("VITRINA_LOGIN")
PASSWORD = os.getenv("VITRINA_PASSWORD")


async def main():
    print("🔍 Диагностика навигации на vitrina.gge.ru/projects")
    print(f"URL: {VITRINA_URL}")
    print(f"Login: {LOGIN}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=os.getenv("HEADLESS", "true").lower() == "true")
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1. Переход на главную
            print("1️⃣  Переход на главную страницу...")
            await page.goto(VITRINA_URL, wait_until="networkidle", timeout=30000)
            print(f"   ✅ URL: {page.url}")
            print(f"   Title: {await page.title()}")
            print()

            # 2. Авторизация
            print("2️⃣  Авторизация...")
            await page.click('a[href="#modal-auth"]', timeout=10000)
            await page.wait_for_selector('#modal-auth', state='visible', timeout=5000)
            await page.fill('#form-login-text', LOGIN)
            await page.fill('#form-passwd-text', PASSWORD)
            await page.click('#login-button-id')
            await page.wait_for_load_state("networkidle", timeout=30000)
            print(f"   ✅ URL после входа: {page.url}")
            print()

            # 3. Переход на /projects/
            print("3️⃣  Переход на /projects/...")
            await page.goto(f"{VITRINA_URL}/projects/", wait_until="networkidle", timeout=60000)
            print(f"   ✅ URL: {page.url}")
            print(f"   Title: {await page.title()}")
            print()

            # 4. Проверка элементов фильтров
            print("4️⃣  Проверка элементов фильтров...")
            await page.wait_for_timeout(3000)
            
            filter_function = await page.query_selector('#filter-function-select-id')
            filter_region = await page.query_selector('#filter-region-select-id')
            filter_expertise = await page.query_selector('#filter-conclusion-text-id')
            
            print(f"   filter-function-select-id: {'✅ найден' if filter_function else '❌ НЕ найден'}")
            print(f"   filter-region-select-id: {'✅ найден' if filter_region else '❌ НЕ найден'}")
            print(f"   filter-conclusion-text-id: {'✅ найден' if filter_expertise else '❌ НЕ найден'}")
            print()

            # 5. Поиск всех select элементов
            print("5️⃣  Поиск всех select элементов...")
            selects = await page.query_selector_all('select')
            print(f"   Найдено select: {len(selects)}")
            for i, select in enumerate(selects[:5]):  # первые 5
                select_id = await select.get_attribute('id')
                select_name = await select.get_attribute('name')
                print(f"   [{i}] id={select_id}, name={select_name}")
            print()

            # 6. Поиск SlimSelect элементов
            print("6️⃣  Поиск SlimSelect элементов...")
            ss_mains = await page.query_selector_all('.ss-main')
            print(f"   Найдено .ss-main: {len(ss_mains)}")
            for i, ss in enumerate(ss_mains[:5]):
                ss_id = await ss.get_attribute('id')
                print(f"   [{i}] id={ss_id}")
            print()

            # 7. Скриншот для визуальной проверки
            screenshot_path = "/tmp/vitrina_debug.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"7️⃣  Скриншот сохранен: {screenshot_path}")
            print()

            print("✅ Диагностика завершена успешно!")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
