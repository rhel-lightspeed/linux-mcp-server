#!/bin/bash

set -euo pipefail

if [[ ! -e /tmp/rpms.in.yaml ]] ; then
    echo "Use RUN --mount=type=bind,source=./rpms.in.yaml,target=/tmp/rpms.in.yaml install-rpms.sh [build|run]"
    exit 1
fi

extract_packages() {
    START_GUARD="<${1^^}_PACKAGES>"
    END_GUARD="<\/${1^^}_PACKAGES>"

    EXTRACT_PACKAGES=$(cat <<EOF
        /$START_GUARD/{flag=1; next}
        /$END_GUARD/{flag=0}
        flag {sub(/^ *- */, ""); print}
EOF
    )

    awk "$EXTRACT_PACKAGES" < /tmp/rpms.in.yaml
}

case $1 in
    build|run)
        mapfile -t PACKAGES < <(extract_packages "$1")
        ;;
    *)
        echo "usage: install-rpms.sh [build|run]" >&2
        exit 1
        ;;
esac

echo "Installing:" "${PACKAGES[@]}"
microdnf -y --nodocs --setopt=install_weak_deps=0 --disableplugin=subscription-manager install "${PACKAGES[@]}"
microdnf --disableplugin=subscription-manager clean all
