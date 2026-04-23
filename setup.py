# RHEL 9 ships setuptools < 61 which cannot read the [project] table from
# pyproject.toml (PEP 621). Read pyproject metadata here and pass it to
# setup() so older setuptools can still build the package correctly.
import sys

from setuptools import find_packages
from setuptools import setup


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

pyproject_settings = {}
with open("pyproject.toml", "rb") as f:
    pyproject_settings = tomllib.load(f)

project = pyproject_settings["project"]

entry_points: dict[str, list[str]] = {"console_scripts": []}
for script_name, script_path in project.get("scripts", {}).items():
    entry_points["console_scripts"].append(f"{script_name} = {script_path}")

long_description = None
with open(
    project["readme"], mode="r", encoding="utf-8"
) as handler:
    long_description = handler.read()

authors = project.get("authors", [{}])
author_name = authors[0].get("name", "") if authors else ""
author_email = authors[0].get("email", "") if authors else ""

setup(
    name=project["name"],
    version=project.get("version", "0.0.0"),
    author=author_name,
    author_email=author_email,
    description=project["description"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=project.get("urls", {}).get("Source code", ""),
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    # Include compiled extensions (.so) from vendored packages like pydantic_core.
    # setuptools only includes .py files by default.
    package_data={"": ["*.so"]},
    install_requires=project.get("dependencies", []),
    entry_points=entry_points,
    classifiers=project.get("classifiers", []),
    python_requires=project.get("requires-python", ">=3.10"),
)
