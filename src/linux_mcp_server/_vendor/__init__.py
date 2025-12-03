# (c) 2020 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import pathlib
import pkgutil
import sys
import warnings


"""
This package exists to allow downstream packagers to transparently vendor Python
packages. It is called very early on to ensure that packages are available.

Packages should be vendored only when necessary. When available, packages from
the system package manager should be used.

A warning will be displayed in the event that a module from this package is
already loaded. That should be a rare, if ever, occuerence due to the natue
of this application.

Packages in this directory are added to the beginning of sys.path. They will
take precedent over any other packages.

Install packages here during downstream packaging using a command such as:

    pip install --upgrade --target [path to this directory] fastmcp
"""


# Mask modules below this path so they cannot be accessed directly
__path__ = []


def _vendor_paths() -> None:
    # List all the module names in this directory
    vendored_path = str(pathlib.Path(__file__).parent)
    vendored_module_names = {module.name for module in pkgutil.iter_modules([vendored_path])}

    if vendored_module_names:
        if vendored_path in sys.path:
            # If the module path was already loaded, remove it to ensure it is
            # at the beginning of sys.path.
            sys.path.remove(vendored_path)

        # Add the module path to the beginning of sys.path so that vendored
        # modules are prioritized over any others.
        sys.path.insert(0, vendored_path)

        if already_loaded_modules := vendored_module_names.intersection(sys.modules):
            warnings.warn(f"Detected already loaded module(s): {', '.join(sorted(already_loaded_modules))}")


_vendor_paths()
