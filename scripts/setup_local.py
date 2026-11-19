"""Generate local secrets once, preserving an existing environment."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists():
    print(".env already exists; kept unchanged.")
else:
    password = secrets.token_hex(24)
    content = (root / ".env.example").read_text(encoding="utf-8")
    content = content.replace("POSTGRES_PASSWORD=GENERATED_BY_SETUP", f"POSTGRES_PASSWORD={password}")
    content = content.replace("campfire:GENERATED_BY_SETUP@", f"campfire:{password}@")
    content = content.replace("SECRET_KEY=GENERATED_BY_SETUP", f"SECRET_KEY={secrets.token_hex(32)}")
    target.write_text(content, encoding="utf-8")
    target.chmod(0o600)
    print("Created .env. Start: docker compose up -d --build --wait")
