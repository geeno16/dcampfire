from passlib.context import CryptContext

_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__time_cost=1,
    argon2__memory_cost=512,
    argon2__parallelism=1,
)


def hash_secret(secret: str) -> str:
    return _context.hash(secret)


def verify_secret(secret: str, hashed: str) -> bool:
    return _context.verify(secret, hashed)
