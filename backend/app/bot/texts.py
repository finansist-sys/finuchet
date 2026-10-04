"""Bot copy in Russian and English. Values interpolated here are already HTML-escaped by callers."""

from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "start_new": "Привет! Я помогу вести учёт денег.\nОткройте приложение, укажите сколько у вас на картах и наличными — и всё готово.",
        "start_back": "С возвращением! Пишите траты прямо сюда, например: <b>300 кофе</b>",
        "open_app": "Открыть Финучёт",
        "need_onboarding": "Сначала откройте приложение и укажите остатки — это займёт полминуты.",
        "help": (
            "Пишите траты и доходы прямо в чат:\n"
            "<b>300 кофе</b> — расход\n"
            "<b>1.5к такси нал</b> — расход наличными\n"
            "<b>20$ обед</b> — расход со счёта в долларах\n"
            "<b>+50000 зп</b> — доход\n\n"
            "Или нажмите «Расход» / «Доход» внизу."
        ),
        "not_understood": "Не нашёл сумму. Напишите, например: <b>300 кофе</b>",
        "btn_expense": "➖ Расход",
        "btn_income": "➕ Доход",
        "btn_balance": "💰 Баланс",
        "pick_category": "Выберите категорию:",
        "ask_amount": "{emoji} {name}. Сколько?",
        "no_account_currency": "Нет счёта в {currency}. Добавьте его в приложении.",
        "no_accounts": "Нет активных счетов. Добавьте счёт в приложении.",
        "saved": "✓ {amount} · {category} · {account}",
        "no_category": "без категории",
        "btn_category": "Категория",
        "btn_account": "Счёт",
        "btn_undo": "↩ Отменить",
        "btn_back": "‹ Назад",
        "undone": "Запись отменена.",
        "gone": "Эта запись уже удалена.",
        "pick_account": "Выберите счёт:",
        "balance_title": "<b>Счета</b>",
        "balance_total": "Итого: {total}",
        "balance_today": "Сегодня потрачено: {amount}",
        "balance_month": "В этом месяце: потрачено {expense} из {income}",
        "balance_top": "<b>Больше всего</b>",
        "delete_confirm": "Удалить все ваши данные без возможности восстановления?",
        "btn_delete_yes": "Да, удалить всё",
        "btn_cancel": "Отмена",
        "deleted": "Все данные удалены. Чтобы начать заново — /start",
        "cancelled": "Отменено.",
        "nothing_to_delete": "У вас нет сохранённых данных.",
        "privacy": (
            "Мы не храним ваш Telegram ID, имя, username, телефон или почту. "
            "Аккаунт связан с вами только через необратимый хэш. "
            "Удалить всё можно командой /delete_me."
        ),
        "slow_down": "Слишком много сообщений, подождите немного.",
    },
    "en": {
        "start_new": "Hi! I'll help you track your money.\nOpen the app, enter how much you have on cards and in cash — that's it.",
        "start_back": "Welcome back! Type expenses right here, e.g. <b>300 coffee</b>",
        "open_app": "Open Finuchet",
        "need_onboarding": "Please open the app first and enter your balances — it takes half a minute.",
        "help": (
            "Type expenses and income right in the chat:\n"
            "<b>300 coffee</b> — expense\n"
            "<b>1.5k taxi cash</b> — cash expense\n"
            "<b>20$ lunch</b> — expense from a USD account\n"
            "<b>+50000 salary</b> — income\n\n"
            "Or tap “Expense” / “Income” below."
        ),
        "not_understood": "I couldn't find an amount. Try: <b>300 coffee</b>",
        "btn_expense": "➖ Expense",
        "btn_income": "➕ Income",
        "btn_balance": "💰 Balance",
        "pick_category": "Choose a category:",
        "ask_amount": "{emoji} {name}. How much?",
        "no_account_currency": "No account in {currency}. Add one in the app.",
        "no_accounts": "No active accounts. Add one in the app.",
        "saved": "✓ {amount} · {category} · {account}",
        "no_category": "no category",
        "btn_category": "Category",
        "btn_account": "Account",
        "btn_undo": "↩ Undo",
        "btn_back": "‹ Back",
        "undone": "Entry undone.",
        "gone": "This entry was already deleted.",
        "pick_account": "Choose an account:",
        "balance_title": "<b>Accounts</b>",
        "balance_total": "Total: {total}",
        "balance_today": "Spent today: {amount}",
        "balance_month": "This month: spent {expense} of {income}",
        "balance_top": "<b>Top spending</b>",
        "delete_confirm": "Delete all your data permanently?",
        "btn_delete_yes": "Yes, delete everything",
        "btn_cancel": "Cancel",
        "deleted": "All data deleted. To start again — /start",
        "cancelled": "Cancelled.",
        "nothing_to_delete": "You have no saved data.",
        "privacy": (
            "We don't store your Telegram ID, name, username, phone or e-mail. "
            "Your account is linked to you only through a one-way hash. "
            "Delete everything with /delete_me."
        ),
        "slow_down": "Too many messages, please wait a moment.",
    },
}


def t(lang: str, key: str, **kwargs: object) -> str:
    table = TEXTS.get(lang) or TEXTS["ru"]
    text = table.get(key) or TEXTS["ru"][key]
    return text.format(**kwargs) if kwargs else text
