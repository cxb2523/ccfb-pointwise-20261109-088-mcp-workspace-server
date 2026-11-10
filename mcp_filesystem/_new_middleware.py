"""New middleware-based approach for FastMCP 2.x compatibility."""


class UserContextMiddleware(BaseHTTPMiddleware):
    """Middleware to capture X-User-ID and X-Chat-ID headers and set context variables."""

    async def dispatch(self, request: Request, call_next):
        # Extract user_id and chat_id from request headers
        user_id = request.headers.get("x-user-id") or request.query_params.get("user_id")
        chat_id = request.headers.get("x-chat-id") or request.query_params.get("chat_id")

        # Set the context variables for this request
        user_token = user_id_var.set(user_id)
        chat_token = chat_id_var.set(chat_id)

        # Also store session info if we have session_id
        session_id = request.query_params.get("session_id")
        if session_id and (user_id or chat_id):
            set_session_info(session_id, user_id, chat_id)

        try:
            response = await call_next(request)
            return response
        finally:
            user_id_var.reset(user_token)
            chat_id_var.reset(chat_token)


class FilesystemFastMCP(FastMCP):
    """FastMCP with middleware injection for session context and admin routes."""

    def http_app(self, **kwargs):
        """Override http_app to add middleware and custom routes."""
        # Get the base app from parent
        app = super().http_app(**kwargs)

        # Add our middleware for capturing user context
        app.add_middleware(UserContextMiddleware)

        # Add admin and web routes
        self._add_admin_routes(app)

        return app

    def _add_admin_routes(self, app):
        """Add admin API and web UI routes to the app."""

        def get_user_data_dir() -> Path:
            """Get the user data directory path."""
            default_user_data_dir = Path(__file__).parent.parent / "user_data"
            return Path(os.environ.get("MCP_WORKSPACES_DIR", str(default_user_data_dir)))

        def get_web_config() -> Dict[str, Any]:
            cfg = load_config()
            return cfg.get("admin_web", {})

        def get_folder_stats(folder_path: Path) -> Dict[str, Any]:
            """Get statistics for a folder."""
            try:
                stat = folder_path.stat()
                file_count = 0
                dir_count = 0
                total_size = 0
                for item in folder_path.rglob("*"):
                    if item.is_file():
                        file_count += 1
                        total_size += item.stat().st_size
                    elif item.is_dir():
                        dir_count += 1

                return {
                    "path": str(folder_path),
                    "name": folder_path.name,
                    "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "accessed_time": datetime.fromtimestamp(stat.st_atime).isoformat(),
                    "file_count": file_count,
                    "dir_count": dir_count,
                    "total_size": total_size,
                }
            except Exception as e:
                return {"error": str(e)}

        # Admin auth helper
        async def verify_admin_token(request: Request) -> bool:
            config = load_config()
            expected_token = config.get("admin_token")
            if not expected_token:
                return False
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                return token == expected_token
            return False

        # ========== Admin API Endpoints ==========

        async def admin_stats(request: Request):
            if not await verify_admin_token(request):
                return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

            user_data_dir = get_user_data_dir()
            if not user_data_dir.exists():
                return JSONResponse({
                    "success": True,
                    "user_data_dir": str(user_data_dir),
                    "total_workspaces": 0,
                    "unique_users": 0,
                    "total_size_bytes": 0,
                    "total_size_human": "0 B",
                })

            workspaces = [d for d in user_data_dir.iterdir() if d.is_dir()]
            unique_users = set()
            total_size = 0

            for ws in workspaces:
                name = ws.name
                if "_" in name:
                    user_part = name.rsplit("_", 1)[0]
                    unique_users.add(user_part)
                else:
                    unique_users.add(name)

                for f in ws.rglob("*"):
                    if f.is_file():
                        total_size += f.stat().st_size

            def human_size(size):
                for unit in ["B", "KB", "MB", "GB", "TB"]:
                    if size < 1024:
                        return f"{size:.2f} {unit}"
                    size /= 1024
                return f"{size:.2f} PB"

            return JSONResponse({
                "success": True,
                "user_data_dir": str(user_data_dir),
                "total_workspaces": len(workspaces),
                "unique_users": len(unique_users),
                "total_size_bytes": total_size,
                "total_size_human": human_size(total_size),
            })

        async def admin_list_workspaces(request: Request):
            if not await verify_admin_token(request):
                return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

            user_id_filter = request.query_params.get("user_id")
            user_data_dir = get_user_data_dir()

            if not user_data_dir.exists():
                return JSONResponse({"success": True, "workspaces": []})

            workspaces = []
            for ws in user_data_dir.iterdir():
                if not ws.is_dir():
                    continue
                if user_id_filter and not ws.name.startswith(user_id_filter):
                    continue
                workspaces.append(get_folder_stats(ws))

            return JSONResponse({"success": True, "workspaces": workspaces})

        async def admin_workspace_info(request: Request):
            if not await verify_admin_token(request):
                return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

            workspace_id = request.path_params.get("workspace_id")
            user_data_dir = get_user_data_dir()
            ws_path = user_data_dir / workspace_id

            if not ws_path.exists() or not ws_path.is_dir():
                return JSONResponse({"success": False, "error": "Workspace not found"}, status_code=404)

            return JSONResponse({"success": True, "workspace": get_folder_stats(ws_path)})

        async def admin_workspace_tree(request: Request):
            if not await verify_admin_token(request):
                return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

            workspace_id = request.path_params.get("workspace_id")
            max_depth = int(request.query_params.get("max_depth", "5"))
            user_data_dir = get_user_data_dir()
            ws_path = user_data_dir / workspace_id

            if not ws_path.exists() or not ws_path.is_dir():
                return JSONResponse({"success": False, "error": "Workspace not found"}, status_code=404)

            def build_tree(path: Path, depth: int = 0):
                if depth > max_depth:
                    return {"name": path.name, "type": "directory", "truncated": True}

                if path.is_file():
                    return {
                        "name": path.name,
                        "type": "file",
                        "size": path.stat().st_size,
                    }

                children = []
                try:
                    for item in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name)):
                        children.append(build_tree(item, depth + 1))
                except PermissionError:
                    pass

                return {
                    "name": path.name,
                    "type": "directory",
                    "children": children,
                }

            return JSONResponse({"success": True, "tree": build_tree(ws_path)})

        async def admin_delete_workspace(request: Request):
            if not await verify_admin_token(request):
                return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)

            workspace_id = request.path_params.get("workspace_id")
            confirm = request.query_params.get("confirm")

            if confirm != "yes":
                return JSONResponse({
                    "success": False,
                    "error": "Add ?confirm=yes to confirm deletion"
                }, status_code=400)

            user_data_dir = get_user_data_dir()
            ws_path = user_data_dir / workspace_id

            if not ws_path.exists() or not ws_path.is_dir():
                return JSONResponse({"success": False, "error": "Workspace not found"}, status_code=404)

            import shutil
            shutil.rmtree(ws_path)

            return JSONResponse({"success": True, "message": f"Workspace {workspace_id} deleted"})

        # ========== Web UI Endpoints ==========

        def web_disabled_response():
            return JSONResponse({"error": "Web UI is disabled"}, status_code=403)

        async def web_tree_endpoint(request: Request):
            web_cfg = get_web_config()
            if not web_cfg.get("enabled", False):
                return web_disabled_response()

            pwd = request.query_params.get("password", "")
            if pwd != web_cfg.get("password", ""):
                return JSONResponse({"error": "Invalid password"}, status_code=401)

            user_data_dir = get_user_data_dir()

            def build_tree(path: Path, rel: str = ""):
                if path.is_file():
                    return {"name": path.name, "type": "file", "path": rel}
                children = []
                try:
                    for item in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name)):
                        child_rel = f"{rel}/{item.name}" if rel else item.name
                        children.append(build_tree(item, child_rel))
                except PermissionError:
                    pass
                return {"name": path.name or "user_data", "type": "directory", "children": children, "path": rel}

            return JSONResponse(build_tree(user_data_dir))

        async def web_file_endpoint(request: Request):
            web_cfg = get_web_config()
            if not web_cfg.get("enabled", False):
                return web_disabled_response()

            pwd = request.query_params.get("password", "")
            if pwd != web_cfg.get("password", ""):
                return JSONResponse({"error": "Invalid password"}, status_code=401)

            file_path = request.query_params.get("path", "")
            user_data_dir = get_user_data_dir()
            target = (user_data_dir / file_path).resolve()

            if not str(target).startswith(str(user_data_dir.resolve())):
                return JSONResponse({"error": "Access denied"}, status_code=403)
            if not target.exists() or not target.is_file():
                return JSONResponse({"error": "File not found"}, status_code=404)

            try:
                content = target.read_text(encoding="utf-8", errors="replace")
                return JSONResponse({"content": content, "name": target.name})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        async def web_index(request: Request):
            web_cfg = get_web_config()
            if not web_cfg.get("enabled", False):
                return web_disabled_response()
            web_dir = Path(__file__).parent / "web"
            return FileResponse(web_dir / "index.html")

        async def web_static(request: Request):
            web_cfg = get_web_config()
            if not web_cfg.get("enabled", False):
                return web_disabled_response()
            rel = request.path_params.get("path") or ""
            web_dir = Path(__file__).parent / "web"
            target = (web_dir / rel).resolve()
            web_root = web_dir.resolve()
            if not str(target).startswith(str(web_root)) or not target.exists() or target.is_dir():
                target = web_root / "index.html"
            return FileResponse(target)

        # Add routes to the app
        app.routes.extend([
            # Admin Web UI
            Route("/admin/api/tree", endpoint=web_tree_endpoint, methods=["GET"]),
            Route("/admin/api/file", endpoint=web_file_endpoint, methods=["GET"]),
            Route("/admin", endpoint=web_index, methods=["GET"]),
            Route("/admin/{path:path}", endpoint=web_static, methods=["GET"]),
            # Admin API routes
            Route("/admin/stats", endpoint=admin_stats, methods=["GET"]),
            Route("/admin/workspaces", endpoint=admin_list_workspaces, methods=["GET"]),
            Route("/admin/workspace/{workspace_id}", endpoint=admin_workspace_info, methods=["GET"]),
            Route("/admin/workspace/{workspace_id}/tree", endpoint=admin_workspace_tree, methods=["GET"]),
            Route("/admin/workspace/{workspace_id}", endpoint=admin_delete_workspace, methods=["DELETE"]),
        ])

