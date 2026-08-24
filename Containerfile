FROM registry.access.redhat.com/ubi10-minimal:10.2-1788137716@sha256:d801168f5e8b108586c27a4fd5c92e3c1e8d061084383713926e2ca61b8b6c64 as base

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

LABEL com.redhat.component=linux-mcp-server
LABEL cpe="cpe:2.3:a:redhat:linux_mcp_server:-:*:*:*:*:*:*:*"
LABEL description="MCP Server for inspecting Linux"
LABEL distribution-scope=private
LABEL io.k8s.description="MCP Server for inspecting Linux"
LABEL io.k8s.display-name="Linux MCP Server"
LABEL io.openshift.tags="rhel,mcp,linux"
LABEL konflux.additional-tags=${VERSION}
LABEL name=linux-mcp-server
LABEL org.opencontainers.image.created=${SOURCE_DATE_EPOCH}
LABEL release=${PSEUDO_VERSION}
LABEL summary="Linux MCP Server"
LABEL url="https://github.com/rhel-lightspeed/linux-mcp-server"
LABEL vendor="Red Hat, Inc."
LABEL version=${VERSION}

ADD licenses/ /licenses/
ADD LICENSE /licenses/Apache-2.0.txt

RUN --mount=type=bind,source=scripts/container-install-rpms.sh,target=/tmp/install-rpms.sh \
    --mount=type=bind,source=./rpms.in.yaml,target=/tmp/rpms.in.yaml \
    /tmp/install-rpms.sh run

COPY --from=build /opt/venvs/mcp /opt/venvs/mcp

RUN useradd --key HOME_MODE=0775 --uid "$UID" --gid 0 --create-home --home-dir "$HOME" mcp

USER mcp
WORKDIR $HOME

CMD ["linux-mcp-server"]
