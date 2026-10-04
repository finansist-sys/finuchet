"""Categories every new user starts with. color = palette slot (0..7), -1 = neutral grey."""

from __future__ import annotations

# (key, ru, en, kind, icon, emoji, color)
DEFAULTS: list[tuple[str, str, str, str, str, str, int]] = [
    ("food", "Продукты", "Groceries", "expense", "cart", "🛒", 0),
    ("cafe", "Кафе", "Cafe", "expense", "coffee", "☕", 1),
    ("transport", "Транспорт", "Transport", "expense", "bus", "🚌", 2),
    ("phone", "Связь", "Phone", "expense", "phone", "📱", 3),
    ("home", "Дом", "Home", "expense", "home", "🏠", 4),
    ("health", "Здоровье", "Health", "expense", "heart", "💊", 5),
    ("fun", "Досуг", "Leisure", "expense", "film", "🎬", 6),
    ("clothes", "Одежда", "Clothes", "expense", "shirt", "👕", 7),
    ("other_exp", "Другое", "Other", "expense", "dots", "•", -1),
    ("salary", "Зарплата", "Salary", "income", "briefcase", "💼", 5),
    ("gift", "Подарок", "Gift", "income", "gift", "🎁", 4),
    ("other_inc", "Другое", "Other", "income", "dots", "•", -1),
]
