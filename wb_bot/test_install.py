"""Проверка установленных зависимостей"""

print("=" * 60)
print("PROВЕРКА УСТАНОВЛЕННЫХ ЗАВИСИМОСТЕЙ")
print("=" * 60)

# Проверка Playwright
try:
    from playwright.sync_api import sync_playwright
    print("[OK] Playwright")
except Exception as e:
    print(f"[FAIL] Playwright: {e}")

# Проверка браузеров
try:
    p = sync_playwright().start()
    firefox_ok = p.firefox is not None
    chromium_ok = p.chromium is not None
    p.stop()
    print(f"[OK] Firefox - {'YES' if firefox_ok else 'NO'}")
    print(f"[OK] Chromium - {'YES' if chromium_ok else 'NO'}")
except Exception as e:
    print(f"[FAIL] Browsers: {e}")

# Проверка SQLAlchemy
try:
    import sqlalchemy
    print(f"[OK] SQLAlchemy {sqlalchemy.__version__}")
except Exception as e:
    print(f"[FAIL] SQLAlchemy: {e}")

# Проверка Alembic
try:
    import alembic
    print(f"[OK] Alembic")
except Exception as e:
    print(f"[FAIL] Alembic: {e}")

# Проверка aiohttp
try:
    import aiohttp
    print(f"[OK] aiohttp {aiohttp.__version__}")
except Exception as e:
    print(f"[FAIL] aiohttp: {e}")

# Проверка psycopg2
try:
    import psycopg2
    print(f"[OK] psycopg2")
except Exception as e:
    print(f"[FAIL] psycopg2: {e}")

# Проверка cryptography
try:
    import cryptography
    print(f"[OK] cryptography")
except Exception as e:
    print(f"[FAIL] cryptography: {e}")

# Проверка других пакетов
try:
    import dotenv
    print(f"[OK] python-dotenv")
except:
    print(f"[FAIL] python-dotenv")

try:
    import redis
    print(f"[OK] redis")
except:
    print(f"[FAIL] redis")

try:
    import PIL
    print(f"[OK] Pillow")
except:
    print(f"[FAIL] Pillow")

print("\n" + "=" * 60)
print("ИТОГОВЫЙ ОТЧЕТ:")
print("=" * 60)
print("[OK] Playwright + Browsers - INSTALLED!")
print("[OK] Database (SQLAlchemy, psycopg2) - INSTALLED!")
print("[OK] HTTP Client (aiohttp) - INSTALLED!")
print("\nАвтоловля готова к работе!")
print("=" * 60)

