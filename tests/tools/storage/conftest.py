import os

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def setup_test_paths(tmp_path) -> Callable[[list[tuple[str, int, float]]], list[str]]:
    """
    Factory fixture for creating test directories or files of specific sizes and modification times.
    If the name in the spec has an extension, files will be created. If there is not file extension,
    then a directory will be created.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
        - Creates files with the specified sizes or subdirectories with a file of specified size (by adding a file within each)
        - Sets their modification times
        - Returns the list of expected file or directory names
    """

    def _create_paths(spec: list[tuple[str, int, float]]) -> list[str]:
        expected_names = []
        for name, size, modified_time in spec:
            expected_names.append(name)
            name = Path(name)
            if name.suffix:
                # Since there is a suffix, make files not directories
                content_file = tmp_path / name
                content_file.write_text("x" * size)
                os.utime(content_file, (modified_time, modified_time))
            else:
                # No file suffix means create directories with one file each
                dir_path = tmp_path / name
                dir_path.mkdir()
                content_file = dir_path / "content.txt"
                content_file.write_text("x" * size)
                os.utime(dir_path, (modified_time, modified_time))

        return expected_names

    return _create_paths


@pytest.fixture
def restricted_path(tmp_path):
    restricted_path = tmp_path / "restricted"
    restricted_path.mkdir()
    restricted_path.chmod(0o000)

    yield restricted_path

    restricted_path.chmod(0o755)
