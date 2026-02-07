# Linux MCP Server Cheatsheet

A quick reference guide for common tasks and the tools to use.

## 🏥 System Health

| I want to check... | Use this tool | Example Prompt |
|-------------------|---------------|----------------|
| **OS / Kernel** | `get_system_information` | "What OS version is this?" |
| **CPU Load** | `get_cpu_information` | "Is the CPU overloaded?" |
| **Memory / RAM** | `get_memory_information` | "How much free RAM do I have?" |
| **Disk Space** | `get_disk_usage` | "Are any disks full?" |
| **Hardware** | `get_hardware_information` | "List the PCI devices." |

## 🔍 Troubleshooting

| I want to check... | Use this tool | Example Prompt |
|-------------------|---------------|----------------|
| **Running Apps** | `list_processes` | "What's using the most CPU?" |
| **Process Details** | `get_process_info` | "Inspect process ID 1234." |
| **Services** | `list_services` | "Are all services running?" |
| **Service Status** | `get_service_status` | "Why did nginx fail?" |
| **System Logs** | `get_journal_logs` | "Show errors from the last hour." |
| **Service Logs** | `get_service_logs` | "Show recent logs for sshd." |
| **Specific Log File** | `read_log_file` | "Read the last 50 lines of /var/log/messages." |

## 📦 Packages (DNF)

| I want to check... | Use this tool | Example Prompt |
|-------------------|---------------|----------------|
| **Installed Packages** | `list_dnf_installed_packages` | "List all installed packages." |
| **Available Packages** | `list_dnf_available_packages` | "What packages are available in repos?" |
| **Package Details** | `get_dnf_package_info` | "Show details for bash." |
| **Repositories** | `list_dnf_repositories` | "Which repositories are enabled?" |

## 🌐 Network

| I want to check... | Use this tool | Example Prompt |
|-------------------|---------------|----------------|
| **IP Addresses** | `get_network_interfaces` | "What is my IP address?" |
| **Open Ports** | `get_listening_ports` | "What ports are open?" |
| **Connections** | `get_network_connections` | "Who is connected to port 22?" |
| **Routes** | `get_ip_route_table` | "Show me the routing table" |

## 📂 Files & Storage

| I want to check... | Use this tool | Example Prompt |
|-------------------|---------------|----------------|
| **Disk Partitions** | `list_block_devices` | "Show me the partition layout." |
| **Large Folders** | `list_directories` | "Find the largest folders in /var." |
| **Recent Changes** | `list_files` | "What files in /etc changed recently?" |

## 💡 Pro Tips

- **Combine Tools:** You don't need to ask for one thing at a time.
  > "Check CPU usage and show me the top 5 processes."
  
- **Filter Logs:** Be specific with time and priority to save context window.
  > "Show me `error` priority logs from the last `30 minutes`."

- **Remote Hosts:** If you configured SSH, just ask to run on a specific host.
  > "Check disk usage on `webserver1`."
