FROM registry.access.redhat.com/ubi10-minimal:10.2-1792742351@sha256:ab67cd02caf8706e34a695a1432ebe965934f6128ec352a6c3f4048b43a4fb5e as base

FROM base as build

RUN --mount=type=bind,source=scripts/container-install-rpms.sh,target=/tmp/install-rpms.sh \
    --mount=type=bind,source=./rpms.in.yaml,target=/tmp/rpms.in.yaml \
    /tmp/install-rpms.sh build

# Build from source by default (Product Security requirement for Konflux).
# Override with --build-arg BUILD_FROM_SOURCE=0 for fast prebuilt-wheel builds.
ARG BUILD_FROM_SOURCE=1

ARG PSEUDO_VERSION=0.1.0a

ENV VENV=/opt/venvs/mcp
ENV SOURCE=/usr/share/container-setup/linux-mcp-server

ENV PATH="$VENV/bin:$PATH"

# Add in source files. The .git directory is used by setuptools-scm to determine
# the release version.
ADD pyproject.toml README.md $SOURCE
ADD src/ $SOURCE/src/
ADD .konflux/ $SOURCE/.konflux/

# Provide the version to avoid the need to pass in the .git directory.
# https://setuptools-scm.readthedocs.io/en/latest/usage/#with-dockerpodman
RUN --mount=type=bind,source=scripts/container-install-app.sh,target=/tmp/install-app.sh \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_LINUX_MCP_SERVER="${PSEUDO_VERSION}" \
    /tmp/install-app.sh

FROM base as final

ARG UID=1001
ARG SOURCE_DATE_EPOCH
ARG PSEUDO_VERSION=0.1.0a
ARG VERSION=0.1.0a

# Indicator the application is running in a container
ENV container=docker

ENV VENV=/opt/venvs/mcp
ENV PATH="${VENV}/bin:$PATH"
ENV HOME=/var/lib/mcp

# Application configuration
ENV LINUX_MCP_SEARCH_FOR_SSH_KEY=True

ARG DESCRIPTION="By using the Model Context Protocol (MCP) server for RHEL, \
you can enable LLMs to act as system administrators, capable of discovering and \
troubleshooting complex issues across your infrastructure"

LABEL com.redhat.component=rhel10/mcp-server-for-rhel
LABEL com.redhat.license_terms="https://www.redhat.com/en/about/red-hat-end-user-license-agreements#rhel"
LABEL cpe="cpe:/o:redhat:enterprise_linux:10.3"
LABEL description="${DESCRIPTION}"
LABEL distribution-scope=restricted
LABEL io.k8s.description="${DESCRIPTION}"
LABEL io.k8s.display-name="MCP Server for RHEL"
LABEL io.openshift.tags="rhel,mcp,linux"
LABEL konflux.additional-tags="${VERSION}"
LABEL name=rhel10/mcp-server-for-rhel
LABEL release=1
LABEL summary="MCP Server for RHEL"
LABEL url="https://github.com/rhel-lightspeed/linux-mcp-server"
LABEL vendor="Red Hat, Inc."
LABEL version="${VERSION}"

ADD licenses/ /licenses/
ADD LICENSE /licenses/Apache-2.0.txt

RUN --mount=type=bind,source=scripts/container-install-rpms.sh,target=/tmp/install-rpms.sh \
    --mount=type=bind,source=./rpms.in.yaml,target=/tmp/rpms.in.yaml \
    /tmp/install-rpms.sh run

COPY --from=build /opt/venvs/mcp /opt/venvs/mcp

RUN useradd --key HOME_MODE=0775 --uid "$UID" --gid 0 --create-home --home-dir "$HOME" mcp

USER mcp
WORKDIR $HOME

# With the server as the entrypoint, arguments given to "podman run" go to it, as in
# "podman run --rm linux-mcp-server --redact-list".
ENTRYPOINT ["linux-mcp-server"]
CMD []
