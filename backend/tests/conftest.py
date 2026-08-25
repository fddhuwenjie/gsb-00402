"""
Shared pytest fixtures/environment.
Sets test database and directory env vars BEFORE any app module is imported,
so services under test never touch the real database.
"""

import os
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="cbom_test_")

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DIR}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["CODE_SCAN_DIR"] = os.path.join(_TEST_DIR, "scans")
