from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.config import Settings
from app.core.datamodel import Store


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.setenv("AAHAAR_WHATSAPP", "simulator")


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


@pytest.fixture()
def cfg(tmp_path):
    return Settings(db_path=str(tmp_path / "test.db"), whatsapp="simulator")


@pytest.fixture()
def seeded(store, cfg):
    from app.core.seed import seed_demo
    pid, wid = seed_demo(store, cfg, days=14,
                         phone="+919000000001", caregiver_phone="+919000000002")
    return pid, wid
