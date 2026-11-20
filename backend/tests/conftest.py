from pathlib import Path

import pytest

from app.core.config import settings
from app.db.database import init_db

REAL_DB_PATH = Path(settings.DB_PATH).resolve()
REAL_MEDIA_DIR = Path(settings.MEDIA_DIR).resolve()
REAL_DB_EXISTS_INITIALLY = REAL_DB_PATH.exists()
REAL_DB_MTIME_INITIALLY = REAL_DB_PATH.stat().st_mtime if REAL_DB_EXISTS_INITIALLY else None
REAL_DB_SIZE_INITIALLY = REAL_DB_PATH.stat().st_size if REAL_DB_EXISTS_INITIALLY else None


@pytest.fixture(scope="session", autouse=True)
def isolate_test_environment(tmp_path_factory):
    """Ensure all tests run against a temporary SQLite database and media directory.
    The real chatmeet.db and real media directory are never created or modified.
    """
    temp_dir = tmp_path_factory.mktemp("test_env")
    temp_db = temp_dir / "test_chatmeet.db"
    temp_media = temp_dir / "media"
    temp_media.mkdir(parents=True, exist_ok=True)

    settings.DB_PATH = str(temp_db)
    settings.MEDIA_DIR = str(temp_media)

    init_db()

    yield {
        "real_db_path": REAL_DB_PATH,
        "real_media_dir": REAL_MEDIA_DIR,
        "real_db_exists": REAL_DB_EXISTS_INITIALLY,
        "real_db_mtime": REAL_DB_MTIME_INITIALLY,
        "real_db_size": REAL_DB_SIZE_INITIALLY,
        "temp_db": temp_db,
        "temp_media": temp_media,
    }

    # Verify real DB file was not touched during the entire session
    if REAL_DB_EXISTS_INITIALLY:
        assert REAL_DB_PATH.exists()
        assert REAL_DB_PATH.stat().st_mtime == REAL_DB_MTIME_INITIALLY
        assert REAL_DB_PATH.stat().st_size == REAL_DB_SIZE_INITIALLY
    else:
        assert not REAL_DB_PATH.exists()
