"""Single-container hosting: the backend serves the Mini App with page headers, safely."""

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from tests.conftest import BOT_TOKEN


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "webapp"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>mini app</title>", encoding="utf-8")
    (root / "assets" / "app-123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside of the site", encoding="utf-8")
    return root


@pytest.fixture
async def client(site, tmp_path):
    settings = Settings(
        env="test",
        bot_token=BOT_TOKEN,
        webhook_secret="s",
        webhook_path_token="p",
        id_pepper="p" * 48,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'db.db').as_posix()}",
        bot_mode="off",
        static_dir=str(site),
        railway_public_domain="finuchet-production.up.railway.app",
    )
    assert settings.public_url == "https://finuchet-production.up.railway.app"
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://t") as c:
        yield c


async def test_index_and_spa_fallback_have_page_csp(client):
    for path in ("/", "/history", "/some/deep/link"):
        r = await client.get(path)
        assert r.status_code == 200 and "mini app" in r.text
        assert "script-src 'self' https://telegram.org" in r.headers["content-security-policy"]
        assert "frame-ancestors 'self' https://web.telegram.org" in r.headers["content-security-policy"]
        assert r.headers["cache-control"] == "no-cache"


async def test_assets_are_cached(client):
    r = await client.get("/assets/app-123.js")
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]


async def test_api_keeps_strict_headers_and_unknown_api_is_404(client):
    r = await client.get("/api/currencies")
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert r.headers["cache-control"] == "no-store"
    assert (await client.get("/api/does-not-exist")).status_code == 404
    assert (await client.get("/tg/whatever")).status_code in (404, 405)


@pytest.mark.parametrize(
    "path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt", "/..%2fsecret.txt"]
)
async def test_path_traversal_never_leaves_the_site(client, path):
    r = await client.get(path)
    assert "outside of the site" not in r.text
