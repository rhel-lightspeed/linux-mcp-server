import os

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def setup_test_directory(tmp_path) -> Callable[[list[tuple[str, int, float]]], tuple[Path, list[str]]]:
    """
    Factory fixture for creating test directories with subdirectories of specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
    - Creates subdirectories with the specified sizes (by adding a file within each)
    - Sets their modification times
    - Returns the directory path and list of expected directory names
    """

    def _create_directory(dir_specs: list[tuple[str, int, float]]) -> tuple[Path, list[str]]:
        """
        Create a directory structure with specified subdirectories.

        Args:
            dir_specs: List of (name, size, modified_time) tuples

        Returns:
            Tuple of (directory_path, expected_names)
        """
        expected_names = []

        for name, size, modified_time in dir_specs:
            dir_path = tmp_path / name
            dir_path.mkdir()

            content_file = dir_path / "content.txt"
            content_file.write_text("x" * size)

            os.utime(dir_path, (modified_time, modified_time))

            expected_names.append(name)

        return tmp_path, expected_names

    return _create_directory


@pytest.fixture
def setup_test_files(tmp_path) -> Callable[[list[tuple[str, int, float]]], tuple[Path, list[str]]]:
    """
    Factory fixture for creating test files of specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
    - Creates files with the specified sizes
    - Sets their modification times
    - Returns the directory path and list of expected file names
    """

    def _create_files(file_specs: list[tuple[str, int, float]]) -> tuple[Path, list[str]]:
        """
        Create files with specified attributes.

        Args:
            file_specs: List of (name, size, modified_time) tuples

        Returns:
            Tuple of (directory_path, expected_names)
        """
        expected_names = []

        for name, size, modified_time in file_specs:
            content_file = tmp_path / name
            content_file.write_text("x" * size)

            os.utime(content_file, (modified_time, modified_time))

            expected_names.append(name)

        return tmp_path, expected_names

    return _create_files


@pytest.fixture
def restricted_path(tmp_path):
    restricted_path = tmp_path / "restricted"
    restricted_path.mkdir()
    restricted_path.chmod(0o000)

    yield restricted_path

    restricted_path.chmod(0o755)


@pytest.fixture
def mock_execute_with_fallback(mock_execute_with_fallback_for):
    return mock_execute_with_fallback_for("linux_mcp_server.commands")
