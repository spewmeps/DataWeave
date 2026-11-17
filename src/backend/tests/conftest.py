from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


# Application singletons are created while test modules are imported. Point
# them at an isolated database before collection so tests never write demo data
# into the developer's persistent src/.data directory.
_created_test_data_dir: Path | None = None
if "DATAWEAVE_DATA_DIR" not in os.environ:
    _created_test_data_dir = Path(tempfile.mkdtemp(prefix="dataweave-tests-"))
    os.environ["DATAWEAVE_DATA_DIR"] = str(_created_test_data_dir)


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    del session, exitstatus
    if _created_test_data_dir is not None:
        shutil.rmtree(_created_test_data_dir, ignore_errors=True)
