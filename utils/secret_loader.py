from codex.tasks.secrets import retrieve_secret


def get_credential(name: str) -> str | None:
    return retrieve_secret(name)
