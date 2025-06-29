#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Navigate to the project root (assuming scripts/ is one level down from root)
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT" || exit 1

echo "🚀 启动桥梁工程知识图谱平台..."
echo "================================================"
echo "Project Root: $(pwd)"
echo "================================================"

# 1. Check for Docker and Docker Compose
echo "🔎 检查 Docker 和 Docker Compose..."
if ! command -v docker &> /dev/null
then
    echo "❌ Docker 未安装. 请先安装 Docker."
    exit 1
fi
docker_version=$(docker --version)
echo "✅ Docker 已找到: $docker_version"

# Check for docker-compose (v1) or docker compose (v2)
if command -v docker-compose &> /dev/null
then
    COMPOSE_CMD="docker-compose"
    compose_version=$(docker-compose --version)
    echo "✅ Docker Compose (v1) 已找到: $compose_version"
elif docker compose version &> /dev/null
then
    COMPOSE_CMD="docker compose"
    compose_version=$(docker compose version)
    echo "✅ Docker Compose (v2) 已找到: $compose_version"
else
    echo "❌ Docker Compose 未安装. 请先安装 Docker Compose (v1 or v2)."
    exit 1
fi
echo "------------------------------------------------"

# 2. Ensure .env files are present
# Check for backend/.env.backend
if [ ! -f "backend/.env.backend" ]; then
    echo "⚠️ backend/.env.backend 文件未找到."
    if [ -f "backend/.env.backend.example" ]; then
        echo "📄 从 backend/.env.backend.example 复制默认配置到 backend/.env.backend..."
        cp "backend/.env.backend.example" "backend/.env.backend"
        echo "✅ backend/.env.backend 已创建. 请根据需要修改此文件."
    else
        echo "❌ backend/.env.backend.example 也未找到. 无法自动创建 backend/.env.backend. 请手动创建."
        # exit 1 # Decide if this is a fatal error
    fi
fi

# Check for neo4j/.env.neo4j
if [ ! -f "neo4j/.env.neo4j" ]; then
    echo "⚠️ neo4j/.env.neo4j 文件未找到."
    if [ -f "neo4j/.env.neo4j.example" ]; then
        echo "📄 从 neo4j/.env.neo4j.example 复制默认配置到 neo4j/.env.neo4j..."
        cp "neo4j/.env.neo4j.example" "neo4j/.env.neo4j"
        echo "✅ neo4j/.env.neo4j 已创建. 请根据需要修改此文件."
    else
        echo "❌ neo4j/.env.neo4j.example 也未找到. 无法自动创建 neo4j/.env.neo4j. 请手动创建."
        # exit 1 # Decide if this is a fatal error
    fi
fi
echo "------------------------------------------------"

# 3. Start services using Docker Compose
echo "🐳 正在使用 Docker Compose 启动所有服务 (Neo4j, Backend, Frontend)..."
echo "这将包括构建镜像（如果需要），可能需要一些时间。"
# Pulling images first can sometimes resolve issues with specific service versions
# $COMPOSE_CMD pull
$COMPOSE_CMD up -d --build --remove-orphans
if [ $? -ne 0 ]; then
    echo "❌ Docker Compose 启动失败. 请检查上面的错误日志."
    echo "尝试运行 '$COMPOSE_CMD up --build' (不带 -d) 查看实时日志."
    exit 1
fi
echo "✅ Docker Compose 服务已启动."
echo "------------------------------------------------"

# 4. Health Checks
echo "🩺 执行健康检查 (等待服务初始化)..."
MAX_WAIT_SECONDS=180 # Max wait 3 minutes
INTERVAL_SECONDS=10
elapsed_seconds=0

# Health check for Neo4j
echo "⏳ 等待 Neo4j 启动 (最长 $MAX_WAIT_SECONDS 秒)..."
NEO4J_READY=false
while [ $elapsed_seconds -lt $MAX_WAIT_SECONDS ]; do
    NEO4J_STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:7474)
    if [ "$NEO4J_STATUS_CODE" = "200" ]; then
        echo "✅ Neo4j 服务已就绪 (HTTP $NEO4J_STATUS_CODE at http://localhost:7474)."
        NEO4J_READY=true
        break
    fi
    # echo "Neo4j 未就绪 (HTTP $NEO4J_STATUS_CODE), 等待 $INTERVAL_SECONDS 秒... ($elapsed_seconds/$MAX_WAIT_SECONDS)"
    sleep $INTERVAL_SECONDS
    elapsed_seconds=$((elapsed_seconds + INTERVAL_SECONDS))
    printf "." # Progress indicator
done
echo "" # Newline after progress dots

if [ "$NEO4J_READY" = false ]; then
    echo "❌ Neo4j 未能在 $MAX_WAIT_SECONDS 秒内就绪 (HTTP $NEO4J_STATUS_CODE). 请检查 '$COMPOSE_CMD logs neo4j'."
    # Optionally, stop services if a critical one fails
    # echo "🛑 停止所有服务..."
    # $COMPOSE_CMD down
    # exit 1
fi
echo "------------------------------------------------"

# Health check for Backend
if [ "$NEO4J_READY" = true ]; then # Only check backend if Neo4j is ready (or skip this dependency if appropriate)
    echo "⏳ 等待后端服务启动 (最长 $MAX_WAIT_SECONDS 秒)..."
    elapsed_seconds=0 # Reset timer for backend
    BACKEND_READY=false
    while [ $elapsed_seconds -lt $MAX_WAIT_SECONDS ]; do
        BACKEND_STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
        if [ "$BACKEND_STATUS_CODE" = "200" ]; then
            echo "✅ 后端服务已就绪 (HTTP $BACKEND_STATUS_CODE at http://localhost:8000/health)."
            BACKEND_READY=true
            break
        fi
        # echo "后端服务未就绪 (HTTP $BACKEND_STATUS_CODE), 等待 $INTERVAL_SECONDS 秒... ($elapsed_seconds/$MAX_WAIT_SECONDS)"
        sleep $INTERVAL_SECONDS
        elapsed_seconds=$((elapsed_seconds + INTERVAL_SECONDS))
        printf "."
    done
    echo ""

    if [ "$BACKEND_READY" = false ]; then
        echo "❌ 后端服务未能在 $MAX_WAIT_SECONDS 秒内就绪 (HTTP $BACKEND_STATUS_CODE). 请检查 '$COMPOSE_CMD logs backend'."
    fi
else
    echo "⚠️ 跳过后端健康检查，因为 Neo4j 未就绪."
fi
echo "------------------------------------------------"

# Health check for Frontend
if [ "$BACKEND_READY" = true ]; then # Only check frontend if backend is ready
    echo "⏳ 等待前端服务启动 (最长 $MAX_WAIT_SECONDS 秒)..."
    elapsed_seconds=0 # Reset timer for frontend
    FRONTEND_READY=false
    while [ $elapsed_seconds -lt $MAX_WAIT_SECONDS ]; do
        FRONTEND_STATUS_CODE=$(curl -s -L -o /dev/null -w "%{http_code}" http://localhost:80) # Added -L to follow redirects
        # Nginx might return 200 for index, or other codes for assets.
        # A successful connection and any 2xx, 3xx (redirects), or even 404 (for SPA main page) could be 'responsive'.
        if [ "$FRONTEND_STATUS_CODE" -ge 200 ] && [ "$FRONTEND_STATUS_CODE" -lt 500 ]; then
            echo "✅ 前端服务已响应 (HTTP $FRONTEND_STATUS_CODE at http://localhost:80)."
            FRONTEND_READY=true
            break
        fi
        # echo "前端服务未响应 (HTTP $FRONTEND_STATUS_CODE), 等待 $INTERVAL_SECONDS 秒... ($elapsed_seconds/$MAX_WAIT_SECONDS)"
        sleep $INTERVAL_SECONDS
        elapsed_seconds=$((elapsed_seconds + INTERVAL_SECONDS))
        printf "."
    done
    echo ""

    if [ "$FRONTEND_READY" = false ]; then
        echo "⚠️ 前端服务未能在 $MAX_WAIT_SECONDS 秒内正确响应 (HTTP $FRONTEND_STATUS_CODE). 请检查 '$COMPOSE_CMD logs frontend'."
    fi
else
    echo "⚠️ 跳过前端健康检查，因为后端服务未就绪."
fi
echo "================================================"

echo "🎉 桥梁工程知识图谱平台部署尝试完成！"
echo ""
echo "可访问地址:"
echo "  - 前端应用: http://localhost (或 http://localhost:5173 如果直接运行SvelteKit dev)"
echo "  - 后端 API: http://localhost:8000"
echo "  - 后端 API 文档 (Swagger): http://localhost:8000/docs"
echo "  - Neo4j Browser: http://localhost:7474 (用户: neo4j, 密码: bridge123)"
echo ""
echo "要停止服务, 请运行: $COMPOSE_CMD down"
echo "要查看特定服务日志, 请运行: $COMPOSE_CMD logs -f <service_name> (e.g., backend, neo4j, frontend)"
echo "================================================"
