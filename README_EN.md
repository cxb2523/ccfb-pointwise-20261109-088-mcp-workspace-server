# MCP Workspace Server

**English** | **[中文](./README.md)**

[![License](assets/license-badge.svg)](LICENSE)

🚀 **One MCP, Complete Agent Capabilities!**

**Beyond Filesystem - Complete AI Development Environment** - Enable AI to perform full-stack Web development, data processing, and code execution like Claude Code

> 💡 **Core Value**: No need to integrate multiple MCP tools. **One MCP server** provides complete Agent capabilities including file operations, code execution, web deployment, data processing, and image generation. Ready to use out of the box, an all-in-one solution.

A powerful MCP (Model Context Protocol) server that goes far beyond file system operations. It's a **complete AI development workspace** with code execution, one-click web deployment, wildcard domain support, Excel processing, image generation, and enterprise-grade capabilities.

## ✨ Why Choose Us?

### 🎯 One MCP, Complete Agent Capabilities

**Traditional Approach**: Need to integrate multiple MCP tools to achieve full functionality
- ❌ File operations → Need one MCP
- ❌ Code execution → Need another MCP
- ❌ Web deployment → Need a third MCP
- ❌ Data processing → Need a fourth MCP
- ❌ Image generation → Need a fifth MCP
- **Result**: Complex configuration, difficult maintenance, scattered functionality

**Our Approach**: Just one MCP, all capabilities ready out of the box
- ✅ **File operations** + **Code execution** + **Web deployment** + **Data processing** + **Image generation**
- ✅ **Unified Configuration**: Configure once, enable all
- ✅ **Unified Management**: One service, centralized management
- ✅ **Unified Security**: One security policy, comprehensive protection

We provide a **complete AI development workspace** with capabilities far beyond traditional filesystem servers:

- 🚀 **Web Development**: AI can create full web applications (HTML/CSS/JS) and **deploy them to production with one click**
- 🌐 **Wildcard Domain Deployment**: Support `*.your-domain.com` wildcard domains, each session automatically gets its own subdomain
- 💻 **Code Execution**: Built-in Python 3.12 and Node.js 20 sandbox environments for real-time code execution and debugging
- 📊 **Data Processing**: Complete Excel/CSV processing with templates, formulas, and formatting
- 🎨 **Image Generation**: Multiple image generation methods including Mermaid flowcharts, data charts, and HTML rendering
- 🔍 **Smart Search**: Advanced capabilities like file content search, knowledge base retrieval, and web crawling
- 🔐 **Enterprise Security**: Multi-tenant isolation, path security protection, resource limits, and sandbox execution

### 🎁 All-in-One Advantages

| Traditional Approach | Our Approach |
|---------------------|--------------|
| Need 5+ MCP tools | **Just 1 MCP** |
| Complex configuration, need to integrate one by one | **Ready out of the box, one-click configuration** |
| Scattered functionality, hard to manage | **Centralized functionality, unified management** |
| Inconsistent security policies | **Unified security policy** |
| High maintenance cost | **Simple maintenance** |

**In One Sentence**: One MCP server = Complete Agent capability stack 🚀

### 💡 Typical Use Cases

**Use Case 1: AI-Driven Web Development**
```
AI creates full frontend app → One-click deployment → Gets independent domain access
Example: https://user123_chat456.your-domain.com
```

**Use Case 2: Data Analysis & Visualization**
```
Read Excel → Data processing → Generate charts → Create reports → Deploy showcase page
```

**Use Case 3: Code Development & Testing**
```
Write Python scripts → Execute tests → Fix bugs → Deploy API services
```

## ✨ Key Features

### 🔐 Multi-Tenant Session Isolation

Each user/session has an independent virtual workspace, completely isolated from others.

**Workspace Naming Convention:**

| X-User-ID | X-Chat-ID | Workspace Directory |
|----------|-----------|---------------------|
| `user123` | `chat456` | `user_data/user123_chat456/` |
| `user123` | (empty) | `user_data/user123/` |
| (empty) | `chat456` | `user_data/chat456/` |
| (empty) | (empty) | Uses default global mode |

Pass identity via HTTP headers:
- `X-User-ID`: User unique identifier (optional)
- `X-Chat-ID`: Session unique identifier (optional)

### 🛡️ Virtual Path System

**Fully Virtualized LLM Perspective**: AI models see a clean virtual filesystem with `/` as the root.

```
LLM's View                  Actual Physical Path
─────────────────────────────────────────────────────────
/                    → /server/user_data/user123_chat456/
/todo.txt            → /server/user_data/user123_chat456/todo.txt
/docs/readme.md      → /server/user_data/user123_chat456/docs/readme.md
```

**Benefits:**
- ✅ Does not expose real server directory structure
- ✅ AI platforms cannot access physical path information
- ✅ Simplifies AI file operation commands
- ✅ Enhanced security and privacy protection

### 🔒 Path Security Protection

Built-in multi-layer security mechanisms to prevent path traversal attacks:

```
Attack Attempt                           Result
─────────────────────────────────────────────────
/../../../etc/passwd                 ❌ Blocked
../../../etc/passwd                  ❌ Blocked  
/foo/../../../etc/passwd             ❌ Blocked
/foo/bar/../../..                    ❌ Blocked
```

**Security Mechanisms:**
1. **Path Resolution**: Uses `Path.resolve()` to resolve all `..` and symlinks
2. **Boundary Check**: Validates that resolved paths are within allowed scope
3. **Double Protection**: Even after resolution, paths must be within `allowed_dirs`

### 📡 SSE Transport Protocol

Supports Server-Sent Events (SSE) transport, compatible with various AI platforms:

```
Client                                  Server
   │                                    │
   │──── GET /sse ──────────────────────▶│  Establish SSE connection
   │◀─── SSE: endpoint=/messages?sid=xxx │  Return message endpoint
   │                                    │
   │──── POST /messages?session_id=xxx ─▶│  Send tool calls
   │◀─── SSE: message (response) ───────│  Receive results
```

### 🌐 One-Click Deployment & Wildcard Domain Support

**One-Click Web Deployment**:
- Frontend projects created by AI can be deployed with one click via `preview_frontend` tool
- Automatically generates accessible URLs with HTTPS support
- Supports custom entry files and directory structures

**Wildcard Domain Deployment (Production)**:
```json
{
  "preview": {
    "wildcard_domain": "*.proxy.your-domain.com",
    "use_tls": true
  }
}
```

After configuration, each session automatically gets its own subdomain:
- `user123_chat456.proxy.your-domain.com`
- `user789_chat012.proxy.your-domain.com`

**Benefits**:
- ✅ No manual domain or port configuration needed
- ✅ Automatic isolation, no interference
- ✅ HTTPS support, production-ready
- ✅ Single-port service, simplified deployment

## 📦 Complete Feature List

### 💻 Web Development & Deployment
| Tool | Feature | Highlight |
|------|---------|-----------|
| `fs_write` | Create web files (HTML/CSS/JS) | Auto-detects format, supports full frontend projects |
| `preview_frontend` | One-click static frontend deployment | **Supports wildcard domains, auto-generates unique subdomains** |
| `exec` | Execute Python/Node.js code | Sandbox environment, supports real-time debugging |
| `generate_image` | Generate charts and flowcharts | Mermaid, data visualization, HTML rendering |

### 📁 File System Operations
| Tool | Description |
|------|-------------|
| `fs_read` | Read files (supports batch, Excel, line ranges) |
| `fs_write` | Create/overwrite files (auto-detects format) |
| `fs_ops` | File system operations (list/mkdir/move/info/delete) |
| `fs_replace` | Precise file editing using SEARCH/REPLACE diff syntax |
| `fs_search` | Search files (glob=by filename, content=by content regex) |

### 📊 Excel Data Processing
| Tool | Description |
|------|-------------|
| `fs_read` | Read Excel files (supports sheet, range parameters) |
| `fs_write` | Create/overwrite Excel files (auto-detects format) |
| `excel_edit` | Edit Excel (batch update cells, formatting) |
| `list_excel_templates` | List available Excel templates |
| `create_excel_from_template` | Create Excel file from template |

### 🔍 Advanced Capabilities (Optional)
| Tool | Description | Config |
|------|-------------|--------|
| `kb_search` | Enterprise knowledge base glob search | `kb.enabled=true` |
| `kb_read` | Read knowledge base files (returns Markdown) | `kb.enabled=true` |
| `crawl_url` | Crawl web pages and return Markdown | `web_crawl.enabled=true` |
| `web_search` | Web search | `web_search.enabled=true` |

## 🔌 Integration with AI Platforms

### 🎯 Why Choose Us as Your MCP Server?

**We are a powerful All-in-One MCP Server**. With just one configuration, you can provide complete Agent capabilities to your AI platform:

- ✅ **File Operations**: Read, write, search, and edit files
- ✅ **Code Execution**: Python/Node.js sandbox environment
- ✅ **Web Deployment**: One-click frontend deployment with wildcard domain support
- ✅ **Data Processing**: Complete Excel/CSV processing capabilities
- ✅ **Image Generation**: Mermaid flowcharts, data charts
- ✅ **Smart Search**: Knowledge base retrieval, web crawling (optional)

**No need to integrate multiple MCP tools** - one MCP Server meets all your needs!

### 🚀 Supported AI Platforms

We integrate seamlessly with mainstream AI platforms, simple configuration, ready out of the box:

#### Dify

1. **Go to Dify Workflow Configuration**
   - Add **MCP Tool** node
   - Select **SSE** transport protocol

2. **Configure MCP Server Connection**
   ```
   SSE Address: http://your-server:8000/sse
   ```

3. **Set Request Headers (Multi-tenant Isolation)**
   ```
   X-User-ID: {{user_id}}
   X-Chat-ID: {{conversation_id}}
   ```

4. **Done!** Your Dify Agent now has complete file operations, code execution, web deployment capabilities.

#### FastGPT

1. **Go to FastGPT Knowledge Base/App Configuration**
   - Add **External Tool** → **MCP**
   - Select **SSE** transport method

2. **Configure Connection Information**
   ```
   MCP Server URL: http://your-server:8000/sse
   ```

3. **Configure User Identity (Optional, for multi-tenant isolation)**
   ```
   Custom Header:
   X-User-ID: {{userId}}
   X-Chat-ID: {{chatId}}
   ```

4. **Enable Tools**: All tools are automatically available, no need to configure one by one!

#### Cherry Studio

1. **Go to Cherry Studio Settings**
   - Open **MCP Servers** configuration
   - Add new MCP Server

2. **Configure Connection**
   ```json
   {
     "name": "MCP Workspace Server",
     "transport": "sse",
     "url": "http://your-server:8000/sse"
   }
   ```

3. **Set Session Identity (Multi-tenant Support)**
   - Cherry Studio automatically passes user and session information
   - Each session gets an independent workspace

### 💡 Integration Advantages

| Traditional Approach | Using Our All-in-One MCP |
|---------------------|--------------------------|
| Need to configure 5+ different MCP tools | **Just configure 1 MCP Server** |
| Each tool requires separate connection and authentication | **Configure once, enable all** |
| Scattered functionality, hard to manage | **Centralized functionality, unified management** |
| Inconsistent security policies across tools | **Unified security policy, comprehensive protection** |
| High maintenance cost for multiple services | **Simple maintenance, one service handles all** |

### 🎁 Ready-to-Use Capabilities

After configuration, your AI Agent immediately has:

- 📝 **File Operations**: Create, read, edit, search files
- 💻 **Code Execution**: Run Python/Node.js scripts, real-time debugging
- 🌐 **Web Development**: Create frontend apps and deploy to production with one click
- 📊 **Data Processing**: Read, edit Excel, generate reports
- 🎨 **Image Generation**: Create flowcharts, data visualization charts
- 🔍 **Smart Search**: File content search, knowledge base retrieval (if enabled)

**One MCP Server = Complete Agent Capability Stack** 🚀

## 🚀 Quick Start

### Docker Deployment (Recommended)

```bash
# Clone the project
git clone <repository-url>
cd mcp-filesystem

# First deployment: build image and start
docker-compose up -d --build

# After code updates, restart to apply
git pull && docker-compose restart

# View logs
docker-compose logs -f

# Rebuild only when dependencies change
docker-compose up -d --build
```

> 💡 The image contains the runtime environment; code is mounted via volume. To update, just `git pull && docker-compose restart`

> ⚠️ **Important**: This project's runtime environment heavily depends on the Docker base image, which includes a complete Python 3.12, Node.js 20 runtime environment, and all system dependencies (such as Tesseract OCR, image processing libraries, etc.). **Docker deployment is strongly recommended**; local Python execution is not recommended. For local development, ensure all system dependencies are installed.

### Quick Configuration Reference

> 📖 **Detailed Integration Guide**: Please refer to the [🔌 Integration with AI Platforms](#-integration-with-ai-platforms) section above for complete configuration steps for Dify, FastGPT, and Cherry Studio.

**Quick Connection Info**:
- **SSE Address**: `http://your-server:8000/sse`
- **Request Headers** (Multi-tenant isolation):
  - `X-User-ID`: `{{userId}}` or fixed user ID
  - `X-Chat-ID`: `{{chatId}}` or fixed session ID

**Claude Desktop (STDIO Mode)**:

Edit config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mcp-workspace": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp-filesystem",
        "run",
        "run_server.py",
        "/path/to/allowed/dir1",
        "/path/to/allowed/dir2"
      ]
    }
  }
}
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│        AI Platforms (Dify / FastGPT / Cherry Studio)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ SSE + HTTP POST
                              │ Headers: X-User-ID, X-Chat-ID
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            MCP Workspace Server (All-in-One)                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │           Session Management & Identity Recognition      ││
│  │         (user_id + chat_id → workspace_name)            ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Virtual Path Translation Layer              ││
│  │         /todo.txt → /user_data/xxx/todo.txt             ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Path Security Validation                    ││
│  │         PathValidator + Traversal Protection             ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              File Operation Execution                    ││
│  │         FileOperations / AdvancedFileOperations          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Physical Filesystem                     │
│  user_data/                                                 │
│  ├── user1_chat1/                                           │
│  │   ├── todo.txt                                           │
│  │   └── docs/                                              │
│  ├── user1_chat2/                                           │
│  └── user2_chat1/                                           │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Admin API

HTTP endpoints for monitoring, debugging, and operations.

### 🔑 Authentication Configuration

Admin API requires Bearer Token authentication. First configure `config.json`:

```bash
# Copy the example config file
cp config.example.json config.json

# Edit config and set your admin secret
vim config.json
```

```json
{
  "admin_token": "your-secret-admin-token-here"
}
```

All Admin API requests must include the `Authorization` header:

```bash
curl -H "Authorization: Bearer your-secret-admin-token-here" \
     http://localhost:8000/admin/stats
```

> ⚠️ **Security Note**: `config.json` is added to `.gitignore`. Do not commit it to version control.

### Get Server Statistics

```http
GET /admin/stats
Authorization: Bearer <admin_token>
```

**Response Example:**
```json
{
  "success": true,
  "user_data_dir": "/path/to/user_data",
  "total_workspaces": 15,
  "unique_users": 8,
  "total_size_bytes": 1048576,
  "total_size_human": "1.00 MB",
  "active_sessions": 3
}
```

### List All Workspaces

```http
GET /admin/workspaces
GET /admin/workspaces?user_id=user123
Authorization: Bearer <admin_token>
```

### Get Workspace Details

```http
GET /admin/workspace/{workspace_id}
GET /admin/workspace/{workspace_id}/tree?max_depth=5
Authorization: Bearer <admin_token>
```

### Delete Workspace

```http
DELETE /admin/workspace/{workspace_id}?confirm=yes
Authorization: Bearer <admin_token>
```

⚠️ **Warning**: This operation is irreversible! The `?confirm=yes` parameter is required.

## 👤 User Workspace API

Fetch a workspace tree for a specific user/chat without the admin token.

```http
GET /api/workspace/tree?user_id={user_id}&chat_id={chat_id}&max_depth=5
```

- No `Authorization` header required
- Scope is limited to the workspace derived from `user_id + chat_id`
- Each directory only returns the 20 most recently modified items (files or subfolders) to keep responses lightweight

## 🧩 Excel Settings

- `config.json`/`config.example.json` now include an `excel` block for max file size, default read rows, supported formats, and formula scanning toggle.
- Templates: `excel.templates_file` defaults to `excel_templates/templates.json`, with template sources stored in `excel_templates/`. Only `title/desc` are exposed to clients; `create_excel_from_template` copies the source and auto-avoids name conflicts. On first use, copy `templates_example.json` to create `templates.json` and configure template paths according to your actual setup.
- Environment overrides: `MCP_EXCEL_MAX_ROWS`, `MCP_EXCEL_MAX_SIZE_MB`.
- See `docs/EXCEL_TOOLS.md` for tool arguments and examples.

## ⚙️ Startup Settings

- `config.json` now includes an `mcp` block to set `transport` (default `sse`), `host` (default `0.0.0.0`), and `port` (default `18089`).
- CLI flags `--transport/--host/--port` override config values.
- Web admin UI: `config.json` adds an `admin_web` block (`enabled` default `false`, `password` default `123456`). When enabled, open `http://<host>:<port>/admin`, enter the password, and browse the `user_data` tree with inline previews for text/Markdown/CSV.

## 📖 Usage Examples

### 🚀 Complete Web Development Workflow

**Step 1: Create Frontend Project**
```
Tool: fs_write
Arguments: {
  "path": "/index.html",
  "content": "<!DOCTYPE html>..."
}
```

**Step 2: One-Click Deployment**
```
Tool: preview_frontend
Arguments: {
  "entry_file": "index.html"
}
```

**Response**:
```json
{
  "success": true,
  "url": "https://user123_chat456.proxy.your-domain.com/index.html",
  "subdomain": "user123_chat456"
}
```

**Step 3: Access Deployed Application**
- Automatically gets unique subdomain
- Supports HTTPS (if configured)
- No manual port or domain configuration needed

### 💻 Code Execution & Debugging

### Read File (with Line Range)

```
Tool: fs_read
Arguments: {
  "path": "/file.txt",
  "line_range": "100:150"  # Read lines 100-150
}
```

### Batch Read Files

```
Tool: fs_read
Arguments: {
  "path": ["/file1.txt", "/file2.json", "/data.xlsx"]
}
```

### Search Files

```
Tool: fs_search
Arguments: {
  "search_type": "content",  # glob=by filename, content=by content
  "pattern": "function\\s+\\w+\\(",
  "context_lines": 2  # Return 2 lines of context around matches
}
```

### Precise File Editing

```
Tool: fs_replace
Arguments: {
  "path": "/config.py",
  "diff": "------- SEARCH\nDEBUG = True\n========\nDEBUG = False\n+++++++ REPLACE"
}
```

### Execute Python Code

```
Tool: exec
Arguments: {
  "code": "print('Hello, World!')"
}
```

### Execute Python File

```
Tool: exec
Arguments: {
  "file": "/script.py",
  "args": ["--verbose", "input.txt"]
}
```

### Read Excel File

```
Tool: fs_read
Arguments: {
  "path": "/data.xlsx",
  "sheet": "Sheet1",      # Optional, specify worksheet
  "range": "A1:D100"      # Optional, specify range
}
```

### Create Excel File

```
Tool: fs_write
Arguments: {
  "path": "/output.xlsx",
  "content": [
    ["Name", "Age", "City"],
    ["Alice", 30, "Beijing"],
    ["Bob", 25, "Shanghai"]
  ]
}
```

### Edit Excel File

```
Tool: excel_edit
Arguments: {
  "path": "/data.xlsx",
  "edit_type": "cells",
  "sheet": "Sheet1",
  "updates": [
    {"cell": "A1", "value": "Updated Value"}
  ]
}
```

### 🎨 Generate Charts and Flowcharts

```
Tool: generate_image
Arguments: {
  "mermaid_code": "flowchart TD\nA[Start] --> B[Process] --> C[End]"
}
```

Or use HTML rendering for complex charts:
```
Tool: generate_image
Arguments: {
  "html_code": "<html><body><h1>Data Visualization</h1>...</body></html>"
}
```

## 🔐 Security Best Practices

1. **Production Deployment**
   - Use reverse proxy (Nginx) for HTTPS
   - Restrict access by IP or use API key authentication
   - Set reasonable rate limits

2. **Data Isolation**
   - Ensure `X-User-ID` and `X-Chat-ID` are generated from trusted sources
   - Regularly clean up expired session workspaces

3. **Admin API Protection**
   ```nginx
   location /admin/ {
       allow 10.0.0.0/8;
       deny all;
       proxy_pass http://localhost:8000;
   }
   ```

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_WORKSPACES_DIR` | User workspace root directory | `project_dir/user_data` |
| `MCP_ALLOWED_DIRS` | Allowed directories list (global mode) | Current working directory |
| `FASTMCP_PORT` | Server port | `8000` |

## 📄 License

[Apache License 2.0](LICENSE)

## 🤝 Contributing

Issues and Pull Requests are welcome!
