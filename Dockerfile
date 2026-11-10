# MCP Filesystem Server with Python & Node.js Runtime
# 
# This unified container provides:
# - MCP Filesystem Server
# - Python 3.12 with data science libraries
# - Node.js 20 with serve for frontend preview
#
# Build: docker build -t mcp-filesystem .
# Run:   docker run -p 18089:18089 -v ./user_data:/user_data mcp-filesystem

FROM python:3.12-slim

LABEL maintainer="MCP Filesystem Team"
LABEL description="MCP Filesystem Server with Python 3.12 and Node.js 20"
LABEL version="1.0.0"

# ============================================
# Environment Variables
# ============================================
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Node.js version
ENV NODE_VERSION=20

# MCP Server default settings (can be overridden by docker-compose environment)
# FASTMCP_* are the actual variables used by the server
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=18089
ENV MCP_WORKSPACES_DIR=/user_data

# Matplotlib backend for headless operation
ENV MPLBACKEND=Agg

# ============================================
# System Dependencies
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Basic tools
    curl \
    wget \
    git \
    unzip \
    # Build tools (needed for some Python packages)
    build-essential \
    # OCR support
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-eng \
    # Image processing dependencies
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Fonts
    fonts-liberation \
    fonts-noto-cjk \
    # Process utilities
    procps \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Node.js 20
# ============================================
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify Node.js installation
RUN node --version && npm --version

# ============================================
# Node.js Global Packages
# ============================================
# Only install serve for frontend preview (keep it minimal)
RUN npm install -g serve \
    && npm cache clean --force

# ============================================
# Python Dependencies
# ============================================
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Install Playwright Chromium (crawl4ai 依赖浏览器)
RUN python -m playwright install --with-deps chromium

# ============================================
# MCP Server Application
# ============================================
# Copy application code
COPY pyproject.toml README.md /app/
COPY mcp_filesystem/ /app/mcp_filesystem/

# Install the MCP server package
RUN pip install --no-cache-dir -e .

# Copy configuration (if exists)
COPY config.example.json /app/config.json

# ============================================
# User Data Directory
# ============================================
RUN mkdir -p /user_data \
    && chmod 755 /user_data

# ============================================
# Security: Create non-root user for command execution
# ============================================
RUN useradd -m -s /bin/bash -u 1000 sandbox \
    && chown -R sandbox:sandbox /user_data

# ============================================
# Health Check
# ============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${FASTMCP_PORT}/ || exit 1

# ============================================
# Expose Ports
# ============================================
# MCP Server
EXPOSE 18089

# Frontend Preview (range)
EXPOSE 7000-7100

# ============================================
# Startup
# ============================================
WORKDIR /app

# Run as root to allow resource limit setting for child processes
# Command execution uses the sandbox user when needed
# Host/port configured via FASTMCP_HOST and FASTMCP_PORT environment variables
CMD ["python", "-m", "mcp_filesystem"]


