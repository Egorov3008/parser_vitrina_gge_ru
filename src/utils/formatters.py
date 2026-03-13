from datetime import datetime
from typing import Dict, Optional

from src.db.repository import Project


def format_project_notification(project: Project, details: Optional[Dict] = None) -> str:
    """Форматировать уведомление о новом проекте в HTML для Telegram (Вариант А)"""

    html = "🏗️ <b>Новый проект</b>\n\n"

    if project.expertise_num:
        html += f"📋 <b>Номер экспертизы:</b> {escape_html(project.expertise_num)}\n"

    if project.object_name:
        html += f"📍 <b>Объект:</b> {escape_html(project.object_name)}\n"

    if project.expert_org:
        html += f"🏢 <b>Экспертная организация:</b> {escape_html(project.expert_org)}\n"

    if project.developer:
        html += f"👷 <b>Застройщик:</b> {escape_html(project.developer)}\n"

    if project.tech_customer:
        html += f"🔧 <b>Технический заказчик:</b> {escape_html(project.tech_customer)}\n"

    if project.region:
        html += f"📄 <b>Регион:</b> {escape_html(project.region)}\n"

    if project.category:
        html += f"📁 <b>Категория:</b> {escape_html(project.category)}\n"

    # Характеристики из деталей
    if details and "characteristics" in details:
        chars = details["characteristics"]
        if isinstance(chars, dict) and chars:
            html += "\n📊 <b>Характеристики:</b>\n"
            for key, value in chars.items():
                if value:
                    label = format_characteristic_label(key)
                    html += f"• {label}: {escape_html(str(value))}\n"

    # Ссылка на проект
    if project.url:
        html += f"\n🔗 <a href=\"{project.url}\">На портале</a>"

    return html


def format_characteristic_label(key: str) -> str:
    """Форматировать название характеристики"""
    labels = {
        "area": "Площадь",
        "floors": "Этажность",
        "cost": "Стоимость",
        "rooms": "Количество комнат",
        "height": "Высота",
        "volume": "Объём",
        "land_area": "Площадь участка",
        "construction_area": "Площадь застройки",
        "total_area": "Общая площадь",
        "living_area": "Жилая площадь",
        "non_residential_area": "Нежилая площадь",
        "apartments": "Количество квартир",
        "cells": "Количество ячеек",
        "places": "Количество мест",
        "capacity": "Мощность/Производительность",
        "length": "Длина",
        "width": "Ширина",
        "depth": "Глубина",
        "diameter": "Диаметр",
        "weight": "Вес",
        "material": "Материал",
        "year_built": "Год постройки",
        "year_commissioning": "Год ввода в эксплуатацию",
        "reconstruction_year": "Год реконструкции",
        "status": "Статус",
        "purpose": "Назначение",
        "type": "Тип",
        "class": "Класс",
        "category": "Категория",
        "group": "Группа",
        "section": "Секция",
        "block": "Блок",
        "zone": "Зона",
        "district": "Район",
        "address": "Адрес",
        "cadastral_number": "Кадастровый номер",
        "permit_number": "Номер разрешения",
        "contract_number": "Номер договора",
        "contract_date": "Дата договора",
        "contract_sum": "Сумма договора",
        "financing_source": "Источник финансирования",
        "investor": "Инвестор",
        "contractor": "Подрядчик",
        "designer": "Проектировщик",
        "surveyor": "Изыскатель",
        "technical_customer": "Технический заказчик",
        "developer": "Застройщик",
        "expert_org": "Экспертная организация",
    }
    return labels.get(key, key.replace("_", " ").title())


def format_summary(new_count: int) -> str:
    """Форматировать сводку по результатам парсинга"""
    if new_count == 0:
        return "✅ Новые объекты не найдены"

    return f"✅ Найдено новых объектов: <b>{new_count}</b>"


def format_status(run_log: Optional[Dict]) -> str:
    """Форматировать статус последнего запуска"""
    if not run_log:
        return "❌ Запусков еще не было"

    started = run_log.get("started_at", "N/A")
    finished = run_log.get("finished_at", "processing")
    status = run_log.get("status", "unknown")
    new_count = run_log.get("new_count", 0)
    error_msg = run_log.get("error_msg", "")

    status_emoji = {
        "success": "✅",
        "error": "❌",
        "running": "⏳",
        "partial": "⚠️",
    }.get(status, "❓")

    result = f"{status_emoji} <b>Последний запуск</b>\n\n"
    result += f"⏱ <b>Начало:</b> {escape_html(str(started))}\n"
    result += f"⏹ <b>Завершение:</b> {escape_html(str(finished))}\n"
    result += f"🔍 <b>Найдено новых:</b> {new_count}\n"

    if error_msg:
        result += f"\n⚠️ <b>Ошибка:</b> {escape_html(error_msg[:100])}"

    return result


def format_stats(stats: Dict, recent_errors: Optional[list] = None) -> str:
    """Форматировать статистику"""
    result = "📊 <b>Статистика</b>\n\n"
    result += f"📦 <b>Всего проектов:</b> {stats.get('total_projects', 0)}\n"
    result += f"✅ <b>Уведомлено:</b> {stats.get('notified_projects', 0)}\n"
    result += f"📅 <b>Сегодня добавлено:</b> {stats.get('today_projects', 0)}\n"

    if recent_errors:
        result += f"\n⚠️ <b>Последние ошибки ({len(recent_errors)}):</b>\n"
        for error in recent_errors[:3]:
            msg = error.get("error_msg", "Unknown")[:50]
            result += f"  • {escape_html(msg)}\n"

    return result


def format_alert(error_message: str) -> str:
    """Форматировать сообщение об ошибке"""
    return (
        f"🚨 <b>ОШИБКА ПАРСЕРА</b>\n\n"
        f"<code>{escape_html(error_message[:500])}</code>"
    )


def escape_html(text: str) -> str:
    """Экранировать HTML спецсимволы для Telegram"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
