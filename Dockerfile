# Multi-stage build for Linux MCP Server
# Uses Red Hat Universal Base Image (UBI) 9 with Python 3.11

# Stage 1: Builder
FROM registry.access.redhat.com/ubi9/ubi:latest AS builder

USER 0

# Install Python 3.11 and build dependencies
RUN dnf install -y \
    python3.11 \
    python3.11-pip \
    python3.11-devel \
    gcc \
    && dnf clean all

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

# Install uv for dependency management
RUN python3.11 -m pip install --no-cache-dir uv

# Install dependencies
RUN python3.11 -m uv pip install --system --no-cache .

# Stage 2: Runtime
FROM registry.access.redhat.com/ubi9/ubi:latest

# Metadata
LABEL name="linux-mcp-server" \
      vendor="RHEL Lightspeed" \
      version="0.1.0" \
      summary="MCP server for read-only Linux system administration" \
      description="Model Context Protocol server providing diagnostic and troubleshooting tools for RHEL-based systems" \
      io.k8s.description="MCP server for Linux diagnostics" \
      io.k8s.display-name="Linux MCP Server" \
      io.openshift.tags="linux,diagnostics,mcp,rhel"

# Switch to root for setup
USER 0

# Install Python 3.11 and runtime system dependencies
RUN dnf install -y \
    python3.11 \
    python3.11-pip \
    openssh-clients \
    iputils \
    procps-ng \
    util-linux \
    lsof \
    && dnf clean all && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

# Create application user (UID 1001 for OpenShift compatibility)
RUN useradd -u 1001 -r -g 0 -d /app -s /sbin/nologin \
    -c "Linux MCP Server user" mcpserver

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/config /app/ssh-keys && \
    chown -R 1001:0 /app && \
    chmod -R g=u /app

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/lib64/python3.11/site-packages /usr/local/lib64/python3.11/site-packages

# Copy application code
COPY --chown=1001:0 src ./src

# Copy example configuration
COPY --chown=1001:0 hosts.example.yaml ./hosts.example.yaml

# Set Python path
ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

# Configure MCP server for OpenShift
ENV LINUX_MCP_TRANSPORT=streamable-http \
    LINUX_MCP_HOST=0.0.0.0 \
    LINUX_MCP_PORT=8000 \
    LINUX_MCP_LOG_DIR=/app/logs \
    LINUX_MCP_CONFIG_FILE=/app/config/hosts.yaml \
    LINUX_MCP_LOG_LEVEL=INFO \
    HOST=0.0.0.0 \
    PORT=8000

# Expose port for streamable-http transport
EXPOSE 8000

# Switch to non-root user (OpenShift compatible)
USER 1001

# Run the MCP server
CMD ["python", "-m", "linux_mcp_server"]

