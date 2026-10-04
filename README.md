# Финучёт

Простой учёт личных финансов в Telegram: бот для быстрых записей и Mini App с балансом и мини-инфографикой.
Без регистрации, без имени и почты — Telegram ID хранится только в виде необратимого хэша.

*Simple personal finance tracker for Telegram (bot + Mini App). Privacy-first: no names, e-mails or Telegram IDs are stored.*

## Возможности

- **Запись прямо в чате бота**: `300 кофе`, `1.5к такси нал`, `20$ обед`, `+50000 зп`. Категория подбирается сама и запоминает ваш выбор; после записи — кнопки «Категория / Счёт / Отменить».
- **Кнопки** «Расход», «Доход», «Баланс» — для тех, кто не любит печатать.
- **Mini App**: баланс по картам и наличным, траты за месяц из дохода, траты за неделю, история, аналитика по категориям, сверка баланса, переводы между счетами.
- **Несколько валют** без пересчёта: у каждого счёта своя валюта, итоги по каждой валюте отдельно.
- Светлая и тёмная тема Telegram, русский и английский.

## Конфиденциальность и безопасность

- Что хранится и что нет — [PRIVACY.md](PRIVACY.md).
- Как устроена защита и как сообщить об уязвимости — [SECURITY.md](SECURITY.md).

## Устройство

```
Telegram ──► Caddy (HTTPS) ──► /api/*, /tg/*  ──► app (FastAPI + aiogram) ──► PostgreSQL
                         └──► /               ──► Mini App (React, статические файлы)
```

| Папка | Что внутри |
|---|---|
| `backend/` | API для Mini App, Telegram-бот, ядро учёта, миграции, тесты (Python 3.12, FastAPI, aiogram 3, SQLAlchemy) |
| `webapp/` | Mini App (React, TypeScript, Vite) |
| `deploy/` | Caddy, инициализация БД, резервные копии |
| `compose.yml` | Запуск всего на сервере одной командой |
| `scripts/privacy_guard.py` | Проверка перед коммитом: не пускает в репозиторий почту, токены, ключи, личные пути |

## Деплой на сервер

### 1. Что понадобится

- **VPS** с Ubuntu 22.04/24.04, 1 vCPU и 1 ГБ памяти достаточно. Сервер должен находиться там, где `api.telegram.org` доступен напрямую.
- **Домен** (или поддомен) с A-записью на IP сервера, например `finance.example.com`.
- **Бот**: в [@BotFather](https://t.me/BotFather) команда `/newbot` → сохраните токен. Затем `/setjoingroups` → **Disable** (бот работает только в личных чатах).

### 2. Подготовка сервера

```sh
# обновления и автоматические обновления безопасности
sudo apt update && sudo apt -y upgrade && sudo apt -y install unattended-upgrades git ufw
# файрвол: только SSH и веб
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
# Docker (официальный репозиторий: https://docs.docker.com/engine/install/ubuntu/)
curl -fsSL https://get.docker.com | sudo sh
```

Рекомендуется входить по SSH-ключу и отключить вход по паролю (`PasswordAuthentication no` в `/etc/ssh/sshd_config`).

### 3. Настройка

```sh
sudo git clone https://github.com/<you>/<repo>.git /opt/finuchet && cd /opt/finuchet
sudo cp .env.example .env && sudo chmod 600 .env
# сгенерировать случайные значения (по одному на каждую строку):
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
sudo nano .env   # DOMAIN, BOT_TOKEN, WEBHOOK_SECRET, WEBHOOK_PATH_TOKEN, ID_PEPPER, пароли БД
```

> `.env` никогда не попадает в git. `ID_PEPPER` нельзя терять и менять: по нему пользователи «узнаются». Сохраните его отдельно от резервных копий базы (например, в менеджере паролей).

### 4. Запуск

```sh
sudo docker compose up -d --build
sudo docker compose ps          # все сервисы healthy / running
sudo docker compose logs app    # без личных данных: только служебные сообщения
```

При старте приложение само применяет миграции, ставит вебхук и кнопку меню. Откройте бота в Telegram и нажмите `/start`.

### 5. Резервные копии

```sh
sudo chmod +x deploy/backup.sh
sudo crontab -e     # добавить строку:
15 3 * * * /opt/finuchet/deploy/backup.sh >/dev/null 2>&1
```

Копии хранятся 7 дней в `/var/backups/finuchet`. Чтобы шифровать их, установите [age](https://age-encryption.org) и задайте `AGE_RECIPIENT`.

Восстановление в пустую базу: `gunzip -c файл.sql.gz | sudo docker compose exec -T db psql -U finuchet_app -d finuchet`.

### 6. Обновление и обслуживание

```sh
cd /opt/finuchet && sudo git pull && sudo docker compose up -d --build
```

Если токен бота утёк: в @BotFather `/revoke`, новый токен в `.env`, затем `sudo docker compose up -d`.

## Локальная разработка

```sh
# один раз после клонирования — включить проверку приватности перед коммитом
git config core.hooksPath .githooks

# backend (тестовый режим без Telegram: вход под выдуманным пользователем)
cd backend && python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scriptsctivate
pip install -r requirements.txt pytest pytest-asyncio ruff
export ENV=dev BOT_MODE=off DEV_FAKE_TG_ID=1 PUBLIC_URL=http://localhost:5173 \
       DATABASE_URL=sqlite+aiosqlite:///./dev.db BOT_TOKEN=0:dev \
       WEBHOOK_SECRET=dev WEBHOOK_PATH_TOKEN=dev ID_PEPPER=dev-pepper-dev-pepper-dev-pepper-123
alembic upgrade head && uvicorn app.main:create_app --factory --port 8000

# Mini App (в другом окне) → http://localhost:5173
cd webapp && npm ci && npm run dev
```

Чтобы проверить бота с настоящим Telegram локально, используйте отдельного тестового бота и `BOT_MODE=polling`.

Проверки: `pytest`, `ruff check app tests`, `npx vitest run`, `npx tsc -p tsconfig.json --noEmit`, `python scripts/privacy_guard.py all`.

## Дорожная карта

Донаты звёздами Telegram, экспорт в CSV/Excel, игровые механики (ритм недели, уровни), напоминания по желанию, раздел финансовой грамотности. Точки расширения уже заложены: `backend/app/core/features.py` (флаги) и `backend/app/core/events.py` (события учёта).
