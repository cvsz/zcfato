from __future__ import annotations

import os
import re

import pytest

from camfrog_control_server.local_setup import create_local_env


def test_local_environment_uses_distinct_random_secrets_and_private_file(tmp_path) -> None:
    destination = create_local_env(tmp_path / "operator-config")
    settings = dict(
        line.split("=", maxsplit=1) for line in destination.read_text(encoding="utf-8").splitlines()
    )

    assert settings["POSTGRES_DB"] == "camfrog_control"
    assert settings["POSTGRES_USER"] == "control_user"
    assert re.fullmatch(r"[0-9a-f]{64}", settings["POSTGRES_PASSWORD"])
    assert settings["DATABASE_URL"] == (
        f"postgresql+psycopg://control_user:{settings['POSTGRES_PASSWORD']}@db:5432/camfrog_control"
    )
    assert re.fullmatch(r"[0-9a-f]{64}", settings["CONTROL_ADMIN_TOKEN"])
    assert re.fullmatch(r"[0-9a-f]{64}", settings["CONTROL_JWT_SECRET"])
    assert (
        len(
            {
                settings["POSTGRES_PASSWORD"],
                settings["CONTROL_ADMIN_TOKEN"],
                settings["CONTROL_JWT_SECRET"],
            }
        )
        == 3
    )
    if os.name == "posix":
        assert destination.stat().st_mode & 0o777 == 0o600


def test_local_environment_never_overwrites_existing_credentials(tmp_path) -> None:
    config_directory = tmp_path / "operator-config"
    config_directory.mkdir()
    destination = config_directory / ".env"
    destination.write_text("existing operator configuration\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        create_local_env(config_directory)

    assert destination.read_text(encoding="utf-8") == "existing operator configuration\n"
