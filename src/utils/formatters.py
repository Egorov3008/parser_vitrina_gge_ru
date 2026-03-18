from datetime import datetime
from typing import Dict, List, Optional

from src.db.repository import Project


def format_project_notification(project: Project, egrz_results: Optional[List[Dict]] = None) -> str:
    """Форматировать уведомление о новом проекте в HTML для Telegram"""

    html = "🏗 <b>Новый проект на Витрине ГГЭ</b>\n\n"

    if project.expertise_num:
        html += f"📋 <b>Номер экспертизы:</b> {escape_html(project.expertise_num)}\n"

    if project.object_name:
        html += f"🏠 <b>Объект:</b> {escape_html(project.object_name)}\n"

    if project.expert_org:
        html += f"🏛 <b>Экспертная организация:</b> {escape_html(project.expert_org)}\n"

    if project.developer:
        html += f"👷 <b>Застройщик:</b> {escape_html(project.developer)}\n"

    if project.tech_customer:
        html += f"🔧 <b>Технический заказчик:</b> {escape_html(project.tech_customer)}\n"

    if project.category:
        html += f"📂 <b>Категория:</b> {escape_html(project.category)}\n"

    if project.region:
        html += f"📍 <b>Регион:</b> {escape_html(project.region)}\n"

    date = project.published_at or project.updated_at
    if date:
        html += f"📅 <b>Дата публикации:</b> {escape_html(str(date))}\n"

    # Данные ЕГРЗ
    if egrz_results:
        first = egrz_results[0]
        egrz_fields = [
            ("Результат экспертизы", "✅ Результат"),
            ("Вид экспертизы", "📝 Вид экспертизы"),
            ("Адрес объекта", "📍 Адрес"),
            ("Проектировщик", "✏️ Проектировщик"),
        ]
        egrz_lines = []
        for api_key, label in egrz_fields:
            val = first.get(api_key)
            if val:
                egrz_lines.append(f"  {label}: {escape_html(str(val))}")
        if egrz_lines:
            html += f"\n📊 <b>Данные ЕГРЗ:</b>\n"
            html += "\n".join(egrz_lines) + "\n"

    # Ссылка на проект
    if project.url:
        html += f"\n🔗 <a href=\"{project.url}\">Ссылка на проект</a>"

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


def format_teps_file(project: Project, teps: Dict) -> str:
    """
    Форматировать ТЭП (технико-экономические показатели) в текстовый файл.

    Возвращает строку для сохранения в .txt файл.
    """
    lines = []

    # Заголовок с основной информацией
    if project.expertise_num:
        lines.append(f"Номер экспертизы: {project.expertise_num}")
    if project.object_name:
        lines.append(f"Наименование объекта: {project.object_name}")
    if project.url:
        lines.append(f"Ссылка: {project.url}")

    lines.append("")
    lines.append("Технико-экономические показатели:")
    lines.append("-" * 50)

    # Добавить все ТЭП пары
    for key, value in teps.items():
        lines.append(f"{key}: {value}")

    return "\n".join(lines)


def format_egrz_file(project: Project, egrz_results: List[Dict]) -> str:
    """Форматировать данные ЕГРЗ в текстовый файл."""
    lines = []

    # Заголовок
    if project.expertise_num:
        lines.append(f"Номер экспертизы: {project.expertise_num}")
    if project.object_name:
        lines.append(f"Наименование объекта: {project.object_name}")
    if project.url:
        lines.append(f"Ссылка: {project.url}")

    for idx, item in enumerate(egrz_results):
        lines.append("")
        if len(egrz_results) > 1:
            lines.append(f"=== Заключение {idx + 1} ===")
        else:
            lines.append("Данные ЕГРЗ:")
        lines.append("-" * 50)

        for key, value in item.items():
            if key == "ТЭП" and isinstance(value, list):
                lines.append(f"\n{key}:")
                for tep in value:
                    if isinstance(tep, dict):
                        name = tep.get("Name") or tep.get("TprName", "")
                        val = tep.get("Value") or tep.get("TprValue", "")
                        unit = tep.get("Unit") or tep.get("TprUnit", "")
                        if name:
                            line = f"  {name}"
                            if val:
                                line += f": {val}"
                            if unit:
                                line += f" {unit}"
                            lines.append(line)
                    else:
                        lines.append(f"  {tep}")
            else:
                lines.append(f"{key}: {value}")

    return "\n".join(lines)


def escape_html(text: str) -> str:
    """Экранировать HTML спецсимволы для Telegram"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
