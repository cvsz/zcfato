"""Create local Compose credentials outside the repository."""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def create_local_env(config_directory: Path | None = None) -> Path:
    directory = config_directory or Path.home() / ".config" / "zchat-control"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        directory.chmod(0o700)

    password = secrets.token_hex(32)
    admin_token = secrets.token_hex(32)
    jwt_secret = secrets.token_hex(32)
    destination = directory / ".env"
    content = "\n".join(
        (
            "POSTGRES_DB=camfrog_control",
            "POSTGRES_USER=control_user",
            f"POSTGRES_PASSWORD={password}",
            f"DATABASE_URL=postgresql+psycopg://control_user:{password}@db:5432/camfrog_control",
            f"CONTROL_ADMIN_TOKEN={admin_token}",
            f"CONTROL_JWT_SECRET={jwt_secret}",
            "CONTROL_DOCS_ENABLED=false",
            "CONTROL_COMMAND_LEASE_SECONDS=60",
            "CONTROL_COMMAND_MAX_ATTEMPTS=3",
            "CONTROL_DASHBOARD_JWT_TTL=900",
            "CONTROL_API_RATE_LIMIT=240",
            "CONTROL_AUTH_RATE_LIMIT=20",
            "",
        )
    )

    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as env_file:
            env_file.write(content)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

    if os.name == "posix":
        destination.chmod(0o600)
    return destination


def main() -> int:
    try:
        destination = create_local_env()
    except FileExistsError:
        print("A local ZChat Control Server credential file already exists; it was left unchanged.")
        return 1
    print(f"Created local ZChat Control Server credentials at {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
