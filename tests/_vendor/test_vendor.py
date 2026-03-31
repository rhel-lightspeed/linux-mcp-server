import pkgutil
import sys

from pathlib import Path

import pytest


class ModuleInfo:
    def __init__(self, name):
        self.name = name


@pytest.fixture
def reset_vendor():
    import linux_mcp_server

    vendor_path = str(Path(linux_mcp_server.__file__).parent / "_vendor")
    saved_modules = {
        k: v for k, v in sys.modules.items() if k == "linux_mcp_server" or k.startswith("linux_mcp_server.")
    }
    saved_path = list(sys.path)

    [sys.path.remove(path) for path in sys.path if path == vendor_path]
    [sys.modules.pop(package, None) for package in ["linux_mcp_server._vendor", "linux_mcp_server"]]

    yield

    sys.path[:] = saved_path
    for key in list(sys.modules.keys()):
        if key == "linux_mcp_server" or key.startswith("linux_mcp_server."):
            sys.modules.pop(key, None)
    sys.modules.update(saved_modules)


def test_package_masking():
    from linux_mcp_server import _vendor

    assert getattr(_vendor, "__path__") == []


def test_vendored(reset_vendor, mocker):
    mocker.patch.object(pkgutil, "iter_modules", return_value=[ModuleInfo(name="nopers")])

    previous_path = list(sys.path)
    import linux_mcp_server

    vendor_path = str(Path(linux_mcp_server.__file__).parent / "_vendor")
    new_path = list(sys.path)

    assert new_path[0] == vendor_path
    assert new_path[1:] == previous_path


def test_vendored_warning(reset_vendor, mocker):
    mocker.patch.object(pkgutil, "iter_modules", return_value=[ModuleInfo(name="sys"), ModuleInfo(name="pkgutil")])

    previous_path = list(sys.path)
    import linux_mcp_server

    vendor_path = str(Path(linux_mcp_server.__file__).parent / "_vendor")
    new_path = list(sys.path)

    with pytest.warns(UserWarning) as warn:
        linux_mcp_server._vendor._vendor_paths()  # pyright: ignore[reportAttributeAccessIssue]

    assert new_path[0] == vendor_path
    assert new_path[1:] == previous_path
    assert any(["pkgutil, sys" in str(w.message) for w in warn])
