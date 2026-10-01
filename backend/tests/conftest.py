from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = replace(get_settings(), storage_root=tmp_path / "storage")
    with TestClient(create_app(settings)) as test_client:
        yield test_client
