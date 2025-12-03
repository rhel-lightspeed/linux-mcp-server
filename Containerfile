FROM registry.access.redhat.com/ubi10-minimal:10.1-1762952303 as base

FROM base as build

RUN microdnf -y --nodocs --setopt=install_weak_deps=0 install \
        git \
        python3.12 \
        python3.12-pip \
        python-unversioned-command \
    && microdnf clean all

ARG PSEUDO_VERSION=0.1.0a

ENV VENVS=/opt/venvs
ENV UV_PROJECT=/usr/share/container-setup/linux-mcp-server/
ENV UV_PROJECT_ENVIRONMENT="${VENVS}"/mcp
ENV UV_PYTHON=/usr/bin/python
ENV PATH=$VENVS/mcp/bin:"$VENVS/uv/bin:$PATH"

# Provide the version to avoid the need to pass in the .git directory.
# https://setuptools-scm.readthedocs.io/en/latest/usage/#with-dockerpodman
# FIXME: This should be SETUPTOOLS_SCM_PRETEND_VERSION_FOR_${DIST_NAME} but I
#        can't figure out what exactly the value for DIST_NAME should be.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${PSEUDO_VERSION}

# Add in source files. The .git directory is used by setuptools-scm to determine
# the release version.
ADD uv.lock pyproject.toml README.md "$UV_PROJECT"
ADD src/ "$UV_PROJECT"/src/

# Install the application in its own virtual environment
RUN python -m venv /opt/venvs/uv \
    && /opt/venvs/uv/bin/python -m pip install -U pip \
    && /opt/venvs/uv/bin/python -m pip install uv \
    && uv venv --seed "${VENVS}"/mcp \
    && uv sync --no-cache --locked --no-dev --no-editable


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

RUN microdnf -y --nodocs --setopt=install_weak_deps=0 install \
        git \
        openssh \
        python3.12 \
        python-unversioned-command \
    && microdnf clean all

COPY --from=build /opt/venvs/mcp /opt/venvs/mcp

RUN useradd --key HOME_MODE=0775 --uid "$UID" --gid 0 --create-home --home-dir "$HOME" mcp

USER mcp
WORKDIR $HOME

CMD ["linux-mcp-server"]
