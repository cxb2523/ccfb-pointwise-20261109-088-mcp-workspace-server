# MCP Workspace Server

**[English](./README_EN.md)** | **中文**

[![License](assets/license-badge.svg)](LICENSE)

🚀 **只需一个 MCP，就能实现你的完整 Agent 能力！**

**超越文件系统的 AI 开发环境** - 让 AI 像 Claude Code 一样进行完整的 Web 开发、数据处理和代码执行

> 💡 **核心价值**：无需集成多个 MCP 工具，**一个 MCP 服务器**即可提供文件操作、代码执行、Web 部署、数据处理、图像生成等完整的 Agent 能力。开箱即用，一站式解决方案。

一个功能强大的 MCP (Model Context Protocol) 服务器，不仅提供安全的文件系统操作，更是一个**完整的 AI 开发工作空间**。支持代码执行、Web 应用一键部署、泛域名访问、Excel 处理、图像生成等企业级能力。

## ✨ 为什么选择我们？

### 🎯 一个 MCP，完整 Agent 能力

**传统方案**：需要集成多个 MCP 工具才能实现完整功能
- ❌ 文件操作 → 需要一个 MCP
- ❌ 代码执行 → 需要另一个 MCP  
- ❌ Web 部署 → 需要第三个 MCP
- ❌ 数据处理 → 需要第四个 MCP
- ❌ 图像生成 → 需要第五个 MCP
- **结果**：配置复杂、维护困难、功能分散

**我们的方案**：只需一个 MCP，所有能力开箱即用
- ✅ **文件操作** + **代码执行** + **Web 部署** + **数据处理** + **图像生成**
- ✅ **统一配置**：一次配置，全部启用
- ✅ **统一管理**：一个服务，集中管理
- ✅ **统一安全**：一套安全策略，全面保护

我们提供的是**完整的 AI 开发工作空间**，能力远超传统文件系统服务器：

- 🚀 **Web 开发能力**：AI 可以创建完整的 Web 应用（HTML/CSS/JS），并**一键部署到生产环境**
- 🌐 **泛域名部署**：支持 `*.your-domain.com` 泛域名，每个会话自动获得独立子域名访问
- 💻 **代码执行**：内置 Python 3.12 和 Node.js 20 沙盒环境，支持代码实时执行和调试
- 📊 **数据处理**：完整的 Excel/CSV 处理能力，支持模板、公式、格式化
- 🎨 **图像生成**：支持 Mermaid 流程图、数据图表、HTML 渲染等多种图像生成方式
- 🔍 **智能搜索**：文件内容搜索、知识库检索、网页抓取等高级能力
- 🔐 **企业级安全**：多租户隔离、路径安全防护、资源限制、沙盒执行

### 🎁 All-in-One 优势

| 传统方案 | 我们的方案 |
|---------|-----------|
| 需要 5+ 个 MCP 工具 | **只需 1 个 MCP** |
| 配置复杂，需要逐个集成 | **开箱即用，一键配置** |
| 功能分散，难以统一管理 | **功能集中，统一管理** |
| 安全策略不统一 | **统一安全策略** |
| 维护成本高 | **维护简单** |

**一句话总结**：一个 MCP 服务器 = 完整的 Agent 能力栈 🚀

### 💡 典型使用场景

**场景 1：AI 驱动的 Web 开发**
```
AI 创建完整的前端应用 → 一键部署 → 获得独立域名访问
例如：https://user123_chat456.your-domain.com
```

**场景 2：数据分析与可视化**
```
读取 Excel → 数据处理 → 生成图表 → 创建报告 → 部署展示页面
```

**场景 3：代码开发与测试**
```
编写 Python 脚本 → 执行测试 → 修复 Bug → 部署 API 服务
```

## ✨ 核心特性

### 🔐 多租户会话隔离

每个用户/会话拥有独立的虚拟工作空间，完全隔离，互不干扰。

**工作目录命名规则：**

| X-User-ID | X-Chat-ID | 工作目录 |
|----------|-----------|----------|
| `user123` | `chat456` | `user_data/user123_chat456/` |
| `user123` | (空) | `user_data/user123/` |
| (空) | `chat456` | `user_data/chat456/` |
| (空) | (空) | 使用默认全局模式 |

通过 HTTP 请求头传递身份标识：
- `X-User-ID`: 用户唯一标识（可选）
- `X-Chat-ID`: 会话唯一标识（可选）

### 🛡️ 虚拟路径系统

**LLM 视角完全虚拟化**：AI 模型看到的是一个干净的虚拟文件系统，以 `/` 为根目录。

```
LLM 看到的路径          实际物理路径
─────────────────────────────────────────────────────────
/                    → /server/user_data/user123_chat456/
/todo.txt            → /server/user_data/user123_chat456/todo.txt
/docs/readme.md      → /server/user_data/user123_chat456/docs/readme.md
```

**优势：**
- ✅ 不暴露服务器真实目录结构
- ✅ AI 平台无法获知物理路径信息
- ✅ 简化 AI 的文件操作指令
- ✅ 提升安全性和隐私保护

### 🔒 路径安全防护

内置多层安全机制，防止路径遍历攻击：

```
攻击尝试                              结果
─────────────────────────────────────────────────
/../../../etc/passwd                 ❌ 被阻止
../../../etc/passwd                  ❌ 被阻止  
/foo/../../../etc/passwd             ❌ 被阻止
/foo/bar/../../..                    ❌ 被阻止
```

**安全机制：**
1. **路径解析**：使用 `Path.resolve()` 解析所有 `..` 和符号链接
2. **边界检查**：验证解析后的路径是否在允许范围内
3. **双重保护**：即使路径被解析，仍必须在 `allowed_dirs` 内

### 📡 SSE 传输协议

支持 Server-Sent Events (SSE) 传输，适配各类 AI 平台：

```
客户端                                服务器
   │                                    │
   │──── GET /sse ──────────────────────▶│  建立 SSE 连接
   │◀─── SSE: endpoint=/messages?sid=xxx │  返回消息端点
   │                                    │
   │──── POST /messages?session_id=xxx ─▶│  发送工具调用
   │◀─── SSE: message (响应) ───────────│  接收结果
```

### 🌐 一键部署与泛域名支持

**一键部署 Web 应用**：
- AI 创建的前端项目可通过 `preview_frontend` 工具一键部署
- 自动生成可访问的 URL，支持 HTTPS
- 支持自定义入口文件和目录结构

**泛域名部署（生产环境）**：
```json
{
  "preview": {
    "wildcard_domain": "*.proxy.your-domain.com",
    "use_tls": true
  }
}
```

配置后，每个会话自动获得独立子域名：
- `user123_chat456.proxy.your-domain.com`
- `user789_chat012.proxy.your-domain.com`

**优势**：
- ✅ 无需手动配置域名和端口
- ✅ 自动隔离，互不干扰
- ✅ 支持 HTTPS，生产就绪
- ✅ 单端口服务，简化部署

## 📦 完整功能列表

### 💻 Web 开发与部署
| 工具 | 功能 | 亮点 |
|------|------|------|
| `fs_write` | 创建 Web 文件（HTML/CSS/JS） | 自动识别格式，支持完整前端项目 |
| `preview_frontend` | 一键部署静态前端 | **支持泛域名，自动生成独立子域名** |
| `exec` | 执行 Python/Node.js 代码 | 沙盒环境，支持实时调试 |
| `generate_image` | 生成图表和流程图 | Mermaid、数据可视化、HTML 渲染 |

### 📁 文件系统操作
| 工具 | 功能 |
|------|------|
| `fs_read` | 读取文件（支持批量、Excel、行范围） |
| `fs_write` | 创建/覆盖文件（自动识别格式） |
| `fs_ops` | 文件系统操作（list/mkdir/move/info/delete） |
| `fs_replace` | 基于 SEARCH/REPLACE 精确编辑文件 |
| `fs_search` | 搜索文件（glob=按文件名，content=按内容正则） |

### 📊 Excel 数据处理
| 工具 | 功能 |
|------|------|
| `fs_read` | 读取 Excel 文件（支持 sheet、range 参数） |
| `fs_write` | 创建/覆盖 Excel 文件（自动识别格式） |
| `excel_edit` | 编辑 Excel（批量更新单元格、格式化） |
| `list_excel_templates` | 列出可用 Excel 模板 |
| `create_excel_from_template` | 从模板创建 Excel 文件 |

### 🔍 高级能力（可选）
| 工具 | 功能 | 配置项 |
|------|------|--------|
| `kb_search` | 企业知识库 glob 搜索 | `kb.enabled=true` |
| `kb_read` | 读取知识库文件（返回 Markdown） | `kb.enabled=true` |
| `crawl_url` | 抓取网页并返回 Markdown | `web_crawl.enabled=true` |
| `web_search` | 联网搜索 | `web_search.enabled=true` |

## 🔌 与 AI 平台集成

### 🎯 为什么选择我们作为你的 MCP Server？

**我们是强大的 All-in-One MCP Server**，只需一次配置，即可为你的 AI 平台提供完整的 Agent 能力：

- ✅ **文件操作**：读写、搜索、编辑文件
- ✅ **代码执行**：Python/Node.js 沙盒环境
- ✅ **Web 部署**：一键部署前端应用，支持泛域名
- ✅ **数据处理**：Excel/CSV 完整处理能力
- ✅ **图像生成**：Mermaid 流程图、数据图表
- ✅ **智能搜索**：知识库检索、网页抓取（可选）

**无需集成多个 MCP 工具**，一个 MCP Server 即可满足所有需求！

### 🚀 支持的 AI 平台

我们与主流 AI 平台完美集成，配置简单，开箱即用：

#### Dify

1. **进入 Dify 工作流配置**
   - 添加 **MCP Tool** 节点
   - 选择 **SSE** 传输协议

2. **配置 MCP Server 连接**
   ```
   SSE 地址: http://your-server:8000/sse
   ```

3. **设置请求头（多租户隔离）**
   ```
   X-User-ID: {{user_id}}
   X-Chat-ID: {{conversation_id}}
   ```

4. **完成！** 现在你的 Dify Agent 拥有完整的文件操作、代码执行、Web 部署等能力。

#### FastGPT

1. **进入 FastGPT 知识库/应用配置**
   - 添加 **外部工具** → **MCP**
   - 传输方式选择 **SSE**

2. **配置连接信息**
   ```
   MCP Server URL: http://your-server:8000/sse
   ```

3. **配置用户标识（可选，用于多租户隔离）**
   ```
   自定义 Header:
   X-User-ID: {{userId}}
   X-Chat-ID: {{chatId}}
   ```

4. **启用工具**：所有工具自动可用，无需逐个配置！

#### Cherry Studio

1. **进入 Cherry Studio 设置**
   - 打开 **MCP Servers** 配置
   - 添加新的 MCP Server

2. **配置连接**
   ```json
   {
     "name": "MCP Workspace Server",
     "transport": "sse",
     "url": "http://your-server:8000/sse"
   }
   ```

3. **设置会话标识（多租户支持）**
   - Cherry Studio 会自动传递用户和会话信息
   - 每个会话获得独立的工作空间

### 💡 集成优势

| 传统方案 | 使用我们的 All-in-One MCP |
|---------|---------------------------|
| 需要配置 5+ 个不同的 MCP 工具 | **只需配置 1 个 MCP Server** |
| 每个工具需要单独连接和认证 | **一次配置，全部启用** |
| 工具之间功能分散，难以统一管理 | **功能集中，统一管理** |
| 不同工具的安全策略不一致 | **统一安全策略，全面保护** |
| 维护多个服务的成本高 | **维护简单，一个服务搞定** |

### 🎁 开箱即用的能力

配置完成后，你的 AI Agent 立即拥有：

- 📝 **文件操作**：创建、读取、编辑、搜索文件
- 💻 **代码执行**：运行 Python/Node.js 脚本，实时调试
- 🌐 **Web 开发**：创建前端应用并一键部署到生产环境
- 📊 **数据处理**：读取、编辑 Excel，生成报告
- 🎨 **图像生成**：创建流程图、数据可视化图表
- 🔍 **智能搜索**：文件内容搜索、知识库检索（如启用）

**一个 MCP Server = 完整的 Agent 能力栈** 🚀

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd mcp-filesystem

# 首次部署：构建镜像并启动
docker-compose up -d --build

> 如果无法使用docker镜像源，可以先执行 export DOCKER_BUILDKIT=0

# 更新代码后重启生效
git pull && docker-compose restart

# 查看日志
docker-compose logs -f

# 仅当依赖变化时需要重新构建
docker-compose up -d --build
```

> 💡 镜像包含运行环境，代码通过 volume 挂载，更新代码只需 `git pull && docker-compose restart`

> ⚠️ **重要说明**：本项目运行环境高度依赖 Docker 基础镜像，包含完整的 Python 3.12、Node.js 20 运行环境以及所有系统依赖（如 Tesseract OCR、图像处理库等）。**强烈建议使用 Docker 方式部署**，不推荐本地 Python 直接运行。如需本地开发，请确保已安装所有系统依赖。

### 快速配置参考

> 📖 **详细集成说明**：请查看上方的 [🔌 与 AI 平台集成](#-与-ai-平台集成) 章节，包含 Dify、FastGPT、Cherry Studio 的完整配置步骤。

**快速连接信息**：
- **SSE 地址**: `http://your-server:8000/sse`
- **请求头**（多租户隔离）:
  - `X-User-ID`: `{{userId}}` 或固定用户ID
  - `X-Chat-ID`: `{{chatId}}` 或固定会话ID

**Claude Desktop（STDIO 模式）**：

编辑配置文件：
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

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│          AI 平台 (Dify / FastGPT / Cherry Studio)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ SSE + HTTP POST
                              │ Headers: X-User-ID, X-Chat-ID
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              MCP Workspace Server (All-in-One)               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              会话管理 & 身份识别                       │    │
│  │         (user_id + chat_id → workspace_name)        │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              虚拟路径转换层                           │    │
│  │         /todo.txt → /user_data/xxx/todo.txt         │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              路径安全验证                             │    │
│  │         PathValidator + 路径遍历防护                  │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              文件操作执行                             │    │
│  │         FileOperations / AdvancedFileOperations      │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      物理文件系统                            │
│  user_data/                                                 │
│  ├── user1_chat1/                                           │
│  │   ├── todo.txt                                           │
│  │   └── docs/                                              │
│  ├── user1_chat2/                                           │
│  └── user2_chat1/                                           │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 管理员 API

提供 HTTP 接口用于监控、调试和运维。

### 🔑 认证配置

Admin API 需要 Bearer Token 认证。首先配置 `config.json`：

```bash
# 复制示例配置文件
cp config.example.json config.json

# 编辑配置，设置你的管理员密钥
vim config.json
```

```json
{
  "admin_token": "your-secret-admin-token-here"
}
```

所有 Admin API 请求必须携带 `Authorization` 头：

```bash
curl -H "Authorization: Bearer your-secret-admin-token-here" \
     http://localhost:8000/admin/stats
```

> ⚠️ **安全提示**：`config.json` 已添加到 `.gitignore`，请勿将其提交到版本库。

### 获取服务器统计信息

```http
GET /admin/stats
Authorization: Bearer <admin_token>
```

**响应示例：**
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

### 列出所有工作空间

```http
GET /admin/workspaces
GET /admin/workspaces?user_id=user123
Authorization: Bearer <admin_token>
```

### 获取工作空间详情

```http
GET /admin/workspace/{workspace_id}
GET /admin/workspace/{workspace_id}/tree?max_depth=5
Authorization: Bearer <admin_token>
```

### 删除工作空间

```http
DELETE /admin/workspace/{workspace_id}?confirm=yes
Authorization: Bearer <admin_token>
```

⚠️ **警告**：此操作不可逆！必须添加 `?confirm=yes` 参数才能执行删除。

## 👤 用户工作空间 API

为用户提供无需管理员 Token 的工作空间目录树查询。

```http
GET /api/workspace/tree?user_id={user_id}&chat_id={chat_id}&max_depth=5
```

- 不需要 `Authorization` 头
- 仅返回对应 `user_id + chat_id` 组合的工作空间
- 每个目录层级按最近修改时间排序，仅保留前 20 个文件/文件夹，其余直接过滤以节省带宽

## 🧩 Excel 配置

- `config.json`/`config.example.json` 新增 `excel` 段落，用于设置最大文件大小、默认读取行数、支持格式与公式检测开关。
- 模板：`excel.templates_file` 默认指向 `excel_templates/templates.json`，模板源文件放在 `excel_templates/`，对外只暴露 `title/desc`，`create_excel_from_template` 会自动避开重名。首次使用时，请从 `templates_example.json` 复制创建 `templates.json`，并根据实际情况配置模板路径。
- 环境变量覆盖：`MCP_EXCEL_MAX_ROWS`、`MCP_EXCEL_MAX_SIZE_MB`。
- 详细参数与示例见 `docs/EXCEL_TOOLS.md`。

## ⚙️ 启动配置

- `config.json` 中新增 `mcp` 段落，可配置 `transport`（默认 `sse`）、`host`（默认 `0.0.0.0`）、`port`（默认 `18089`）。
- CLI 参数 `--transport/--host/--port` 优先级高于配置文件。
- Web 管理界面：`config.json` 新增 `admin_web` 段落（`enabled` 默认 `false`，`password` 默认 `123456`）。开启后访问 `http://<host>:<port>/admin`，输入密码可查看 user_data 下文件树并预览文本/Markdown/CSV。

## 📖 使用示例

### 🚀 Web 开发完整流程

**步骤 1：创建前端项目**
```
Tool: fs_write
Arguments: {
  "path": "/index.html",
  "content": "<!DOCTYPE html>..."
}
```

**步骤 2：一键部署**
```
Tool: preview_frontend
Arguments: {
  "entry_file": "index.html"
}
```

**返回结果**：
```json
{
  "success": true,
  "url": "https://user123_chat456.proxy.your-domain.com/index.html",
  "subdomain": "user123_chat456"
}
```

**步骤 3：访问部署的应用**
- 自动获得独立子域名
- 支持 HTTPS（如配置）
- 无需手动配置端口和域名

### 💻 代码执行与调试

### 读取文件（支持行范围）

```
Tool: fs_read
Arguments: {
  "path": "/file.txt",
  "line_range": "100:150"  # 读取第100-150行
}
```

### 批量读取文件

```
Tool: fs_read
Arguments: {
  "path": ["/file1.txt", "/file2.json", "/data.xlsx"]
}
```

### 搜索文件

```
Tool: fs_search
Arguments: {
  "search_type": "content",  # glob=按文件名, content=按内容
  "pattern": "function\\s+\\w+\\(",
  "context_lines": 2  # 返回匹配行前后2行上下文
}
```

### 精确编辑文件

```
Tool: fs_replace
Arguments: {
  "path": "/config.py",
  "diff": "------- SEARCH\nDEBUG = True\n========\nDEBUG = False\n+++++++ REPLACE"
}
```

### 执行 Python 代码

```
Tool: exec
Arguments: {
  "code": "print('Hello, World!')"
}
```

### 执行 Python 文件

```
Tool: exec
Arguments: {
  "file": "/script.py",
  "args": ["--verbose", "input.txt"]
}
```

### 读取 Excel 文件

```
Tool: fs_read
Arguments: {
  "path": "/data.xlsx",
  "sheet": "Sheet1",      # 可选，指定工作表
  "range": "A1:D100"      # 可选，指定读取范围
}
```

### 创建 Excel 文件

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

### 编辑 Excel 文件

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

### 🎨 生成图表和流程图

```
Tool: generate_image
Arguments: {
  "mermaid_code": "flowchart TD\nA[开始] --> B[处理] --> C[结束]"
}
```

或使用 HTML 渲染复杂图表：
```
Tool: generate_image
Arguments: {
  "html_code": "<html><body><h1>数据可视化</h1>...</body></html>"
}
```

## 🔐 安全最佳实践

1. **生产环境部署**
   - 使用反向代理（Nginx）处理 HTTPS
   - 限制访问 IP 或使用 API 密钥认证
   - 设置合理的请求频率限制

2. **数据隔离**
   - 确保 `X-User-ID` 和 `X-Chat-ID` 由可信来源生成
   - 定期清理过期的会话工作目录

3. **Admin API 保护**
   ```nginx
   location /admin/ {
       allow 10.0.0.0/8;
       deny all;
       proxy_pass http://localhost:8000;
   }
   ```

## ⚙️ 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MCP_WORKSPACES_DIR` | 用户工作空间根目录 | `项目目录/user_data` |
| `MCP_ALLOWED_DIRS` | 允许访问的目录列表（全局模式） | 当前工作目录 |
| `FASTMCP_PORT` | 服务器端口 | `8000` |

## 📄 许可证

[Apache License 2.0](LICENSE)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
