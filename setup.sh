#!/bin/bash

# 桥梁工程知识图谱平台 - 安装脚本
# 用于快速设置开发环境

set -e  # 遇到错误时退出

echo "🌉 桥梁工程知识图谱平台 - 环境安装"
echo "================================================="

# 检查 Python 版本
check_python() {
    echo "🐍 检查 Python 环境..."
    
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 未安装，请先安装 Python 3.11+"
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "✅ Python $python_version 已安装"
    
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
        echo "✅ Python 版本符合要求 (>= 3.11)"
    else
        echo "⚠️  建议使用 Python 3.11+ 以获得最佳性能"
    fi
}

# 创建虚拟环境
setup_venv() {
    echo ""
    echo "🔧 设置 Python 虚拟环境..."
    
    cd backend
    
    if [ -d "venv" ]; then
        echo "ℹ️  虚拟环境已存在，跳过创建"
    else
        echo "📦 创建虚拟环境..."
        python3 -m venv venv
        echo "✅ 虚拟环境创建完成"
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    echo "✅ 虚拟环境已激活"
    
    # 升级 pip
    echo "📦 升级 pip..."
    pip install --upgrade pip
    
    cd ..
}

# 安装 Python 依赖
install_dependencies() {
    echo ""
    echo "📦 安装 Python 依赖..."
    
    cd backend
    source venv/bin/activate
    
    echo "📥 安装依赖包..."
    pip install -r requirements.txt
    
    echo "✅ Python 依赖安装完成"
    cd ..
}

# 检查 Neo4j
check_neo4j() {
    echo ""
    echo "📊 检查 Neo4j 数据库..."
    
    if command -v neo4j &> /dev/null; then
        echo "✅ Neo4j 已安装"
        
        # 检查 Neo4j 是否运行
        if pgrep -f neo4j > /dev/null; then
            echo "✅ Neo4j 服务正在运行"
        else
            echo "⚠️  Neo4j 未运行，请启动服务"
            echo "   启动命令: neo4j start"
        fi
    else
        echo "❌ Neo4j 未安装"
        echo ""
        echo "📝 Neo4j 安装指南:"
        echo "   macOS: brew install neo4j"
        echo "   Ubuntu: apt install neo4j"
        echo "   或下载: https://neo4j.com/download/"
        echo ""
        echo "⚙️  配置建议:"
        echo "   1. 设置密码: bridge123"
        echo "   2. 启动服务: neo4j start"
        echo "   3. 访问: http://localhost:7474"
    fi
}

# 检查 Ollama
check_ollama() {
    echo ""
    echo "🤖 检查 Ollama AI 环境..."
    
    if command -v ollama &> /dev/null; then
        echo "✅ Ollama 已安装"
        
        # 检查 Ollama 是否运行
        if pgrep -f ollama > /dev/null; then
            echo "✅ Ollama 服务正在运行"
            
            # 检查模型
            echo "🔍 检查 AI 模型..."
            if ollama list | grep -q "qwen2.5:7b"; then
                echo "✅ qwen2.5:7b 模型已安装"
            else
                echo "⚠️  qwen2.5:7b 模型未安装"
                echo "   安装命令: ollama pull qwen2.5:7b"
            fi
            
            if ollama list | grep -q "nomic-embed-text"; then
                echo "✅ nomic-embed-text 模型已安装"
            else
                echo "⚠️  nomic-embed-text 模型未安装"
                echo "   安装命令: ollama pull nomic-embed-text"
            fi
        else
            echo "⚠️  Ollama 未运行，请启动服务"
            echo "   启动命令: ollama serve"
        fi
    else
        echo "❌ Ollama 未安装"
        echo ""
        echo "📝 Ollama 安装指南:"
        echo "   下载: https://ollama.ai/download"
        echo "   或使用: curl -fsSL https://ollama.ai/install.sh | sh"
        echo ""
        echo "⚙️  模型安装:"
        echo "   ollama pull qwen2.5:7b"
        echo "   ollama pull nomic-embed-text"
    fi
}

# 创建环境变量文件
create_env_file() {
    echo ""
    echo "⚙️  创建环境配置文件..."
    
    cd backend
    
    if [ -f ".env" ]; then
        echo "ℹ️  .env 文件已存在，跳过创建"
    else
        echo "📝 创建 .env 配置文件..."
        cat > .env << 'EOF'
# 桥梁工程知识图谱平台 - 环境变量配置

# 基础配置
DEBUG=true
SECRET_KEY=bridge-knowledge-platform-secret-key-change-in-production

# 服务器配置
HOST=0.0.0.0
PORT=8000

# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=bridge123

# Ollama 配置 (本地 AI 模型)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_EMBED_DIM=768

# 文件存储配置
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=104857600

# Graphiti 配置
GRAPHITI_GROUP_ID=bridge_engineering

# CORS 配置
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://localhost:8080"]
EOF
        echo "✅ .env 文件创建完成"
    fi
    
    cd ..
}

# 运行测试
run_tests() {
    echo ""
    echo "🧪 运行平台测试..."
    
    cd backend
    source venv/bin/activate
    
    python test_platform.py
    
    cd ..
}

# 显示下一步指令
show_next_steps() {
    echo ""
    echo "🎉 安装完成！"
    echo "================================================="
    echo ""
    echo "📝 下一步操作："
    echo ""
    echo "1. 确保服务运行："
    echo "   - Neo4j: neo4j start"
    echo "   - Ollama: ollama serve"
    echo ""
    echo "2. 启动平台："
    echo "   cd backend"
    echo "   source venv/bin/activate"
    echo "   uvicorn app.main:app --reload"
    echo ""
    echo "3. 访问服务："
    echo "   - API 文档: http://localhost:8000/docs"
    echo "   - 健康检查: http://localhost:8000/health"
    echo "   - Neo4j 浏览器: http://localhost:7474"
    echo ""
    echo "📚 更多信息请查看 README.md"
}

# 主函数
main() {
    # 创建必要目录
    mkdir -p backend/uploads/{pdf,doc,cad,bim,temp}
    mkdir -p backend/exports
    mkdir -p docs
    
    # 执行安装步骤
    check_python
    setup_venv
    install_dependencies
    create_env_file
    check_neo4j
    check_ollama
    run_tests
    show_next_steps
}

# 运行主函数
main "$@" 