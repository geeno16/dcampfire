"""Export the contract without starting PostgreSQL or SMTP."""
import json
import os
from pathlib import Path

for name, value in {
    "DATABASE_URL": "postgresql+asyncpg://unused:unused@localhost/unused",
    "SECRET_KEY": "openapi-export-only-not-a-server-secret",
    "SMTP_HOST": "localhost",
    "SMTP_PORT": "1025",
    "SMTP_FROM": "campfire@example.test",
}.items():
    os.environ.setdefault(name, value)
from src.main import app  # noqa: E402

target = Path(__file__).resolve().parents[1] / "android/api/openapi.json"
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Exported {len(app.openapi()['paths'])} paths")
