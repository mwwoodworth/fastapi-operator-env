from cryptography.fernet import Fernet
import os

FERNET_SECRET = os.getenv("FERNET_SECRET")

if not FERNET_SECRET:
    raise ValueError("FERNET_SECRET environment variable not set")

fernet = Fernet(FERNET_SECRET)


def encrypt(text: str) -> str:
    return fernet.encrypt(text.encode()).decode()


def decrypt(cipher: str) -> str:
    return fernet.decrypt(cipher.encode()).decode()
