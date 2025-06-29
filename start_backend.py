#!/usr/bin/env python3
"""
桥梁知识图谱平台 - 后端启动脚本
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # 获取项目根目录
    project_root = Path(__file__).parent
    backend_dir = project_root / "backend"
    
    # 检查backend目录是否存在
    if not backend_dir.exists():
        print("❌ 错误: backend目录不存在")
        sys.exit(1)
    
    # 切换到backend目录
    os.chdir(backend_dir)
    print(f"📂 切换到目录: {backend_dir}")
    
    # 检查虚拟环境
    venv_python = project_root / "venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = project_root / "venv" / "Scripts" / "python.exe"  # Windows
    
    if not venv_python.exists():
        print("❌ 错误: 虚拟环境不存在，请先运行 source venv/bin/activate")
        sys.exit(1)
    
    # 检查必要的环境变量
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ 错误: 请设置 OPENAI_API_KEY 环境变量")
        sys.exit(1)
    
    print("🚀 启动桥梁知识图谱平台后端服务...")
    print("📍 服务地址: http://localhost:8000")
    print("📖 API文档: http://localhost:8000/docs")
    print("⏹️  停止服务: Ctrl+C")
    print("-" * 50)
    
    try:
        # 启动服务
        subprocess.run([
            str(venv_python), "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 