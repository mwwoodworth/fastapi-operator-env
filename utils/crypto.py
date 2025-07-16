from cryptography.fernet import Fernet

from core.settings import Settings

settings = Settings()

FERNET_SECRET = settings.FERNET_SECRET

if not FERNET_SECRET:
    raise ValueError("FERNET_SECRET environment variable not set")

fernet = Fernet(FERNET_SECRET)


def encrypt(text: str) -> str:
    return fernet.encrypt(text.encode()).decode()


def decrypt(cipher: str) -> str:
    return fernet.decrypt(cipher.encode()).decode()
