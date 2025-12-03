%global _srcname linux-mcp-server
%global _mcp_version 1.23.0

Name:       python-%{_srcname}
Version:    0.1.0a3
Release:    %autorelease
Summary:    MCP server for read-only Linux system administration.
License:    Apache-2.0
URL:        https://github.com/rhel-lightspeed/linux-mcp-server
Source0:    %{pypi_source linux_mcp_server}
Source1:    %{pypi_source mcp %{_mcp_version}}

BuildSystem: pyproject
BuildOption(install): -l linux_mcp_server
BuildOption(generate_buildrequires): -p

BuildArch:      noarch
BuildRequires:  tomcli
BuildRequires:  git-core
BuildRequires:  python3-devel
BuildRequires:  python3-pip

# TODO(r0x0d): Vendoring the mcp dependency as of now since it is not
# available in Fedora.
Provides: bundled(python3dist(mcp)) = %{_mcp_version}

%global _description %{expand:
MCP server for read-only Linux system administration, diagnostics, and troubleshooting
}

%description %_description

%package -n python3-%{_srcname}
Summary:    %{summary}

%description -n python3-%{_srcname} %_description

%prep -a
# Drop the mcp dependency as we are bundling it from Source1.
tomcli set pyproject.toml arrays delitem project.dependencies "mcp.*"

# Remove dynamic version from pyproject.toml (workaround for packit)
tomcli set pyproject.toml del project.dynamic

# Add version to pyproject.toml (workaround for packit)
tomcli set pyproject.toml str project.version %{version}

# Install mcp to _vendor
%{python3} -m pip install %{SOURCE1} --target src/linux_mcp_server/_vendor

export PIP_FIND_LINKS=$PWD/_vendor
export PYTHONPATH=$PWD/_vendor:$PYTHONPATH

%files -n python3-%{_srcname} -f %{pyproject_files}

%changelog
%autochangelog
