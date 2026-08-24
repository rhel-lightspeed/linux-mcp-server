#!/bin/bash

set -euo pipefail

: "${SOURCE:?SOURCE must be set.}"
: "${VENV:?VENV must be set.}"

/usr/bin/python3.12 -m venv "${VENV}"
PIP="${VENV}/bin/pip"

if [[ -f /cachi2/cachi2.env ]]; then
    # shellcheck disable=SC1091
    . /cachi2/cachi2.env
fi

if [[ $BUILD_FROM_SOURCE = 1 ]] ; then
    NO_BINARY=(--no-binary :all:)
else
    NO_BINARY=()
fi

${PIP} install -U pip
${PIP} install "${NO_BINARY[@]}" -r "$SOURCE/.konflux/requirements.txt"
${PIP} uninstall -y diskcache

${PIP} install "${NO_BINARY[@]}" "$SOURCE"
