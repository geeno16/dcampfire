import asyncio
import json
import sys
from getpass import getpass

import httpx

HOST = "http://localhost:8000"
BASE = f"{HOST}/api/v1"


def _show(label: str, response: httpx.Response) -> None:
    print(f"\n[{label}] -> HTTP {response.status_code}")
    try:
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(response.text or "(пустой ответ)")


def _run_flow(nickname: str, email: str, password: str) -> bool:
    with httpx.Client(base_url=BASE, timeout=30) as client:
        response = client.post(
            "/auth/register",
            json={
                "nickname": nickname,
                "email": email,
                "password": password,
                "pd_consent": True,
            },
        )
        _show("РЕГИСТРАЦИЯ", response)
        if response.status_code != 201:
            return False

        verified = False
        while not verified:
            choice = input(
                "\nКод из письма | 'r' — переотправить | 's' — пропустить: "
            ).strip()
            if choice.lower() == "s":
                break
            if choice.lower() == "r":
                _show(
                    "ПЕРЕОТПРАВКА КОДА",
                    client.post(
                        "/auth/resend-code", json={"email": email}
                    ),
                )
                continue

            response = client.post(
                "/auth/verify-email",
                json={"email": email, "code": choice},
            )
            _show("ПОДТВЕРЖДЕНИЕ", response)
            verified = response.status_code == 200

        if not verified:
            return False

        _show(
            "ВХОД",
            client.post(
                "/auth/login",
                json={"email": email, "password": password},
            ),
        )

    return True


def _server_available() -> bool:
    try:
        httpx.get(f"{HOST}/openapi.json", timeout=3)
    except httpx.TransportError:
        return False
    return True


def main() -> None:
    if not _server_available():
        print(
            f"Сервер не запущен на {HOST} — сначала "
            "запустите задачу «Backend: Запустить dev сервер»"
        )
        sys.exit(1)

    nickname = input("Псевдоним: ").strip()
    email = input("Email: ").strip()
    password = getpass("Пароль: ")

    _run_flow(nickname, email, password)

    if (
        input("\nУдалить тестовый аккаунт из БД? (Y/n): ")
        .strip()
        .lower()
        != "n"
    ):
        from src.common.delete_user_vstask import _delete

        asyncio.run(_delete(email))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано.")
        sys.exit(1)
