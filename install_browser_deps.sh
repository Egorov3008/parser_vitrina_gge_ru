#!/bin/bash

# Скрипт установки системных зависимостей для Playwright Chromium
# Выполняется один раз при первой настройке проекта

set -e

echo "================================================"
echo "Установка системных зависимостей для Playwright"
echo "================================================"
echo ""

# Проверяем, запущен ли скрипт с правами sudo
if [ "$EUID" -ne 0 ]; then
    echo "❌ Этот скрипт требует права администратора (sudo)"
    echo ""
    echo "Запустите:"
    echo "  sudo bash ./install_browser_deps.sh"
    echo ""
    exit 1
fi

echo "📦 Обновляем список пакетов..."
apt-get update

echo ""
echo "📚 Устанавливаем системные библиотеки для Chromium..."
apt-get install -y \
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
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcursor1 \
    libxext6 \
    libxfixes3 \
    libxinerama1 \
    libxrandr2 \
    libxrender1 \
    libxext6 \
    libgtk-3-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0

echo ""
echo "✅ Системные зависимости установлены успешно!"
echo ""
echo "Теперь активируйте виртуальное окружение и убедитесь,"
echo "что Playwright Chromium установлен:"
echo ""
echo "  source venv/bin/activate"
echo "  playwright install chromium"
echo ""
echo "Затем запустите парсер:"
echo "  python -m src.main"
echo ""
