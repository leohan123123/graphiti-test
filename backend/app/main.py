"""
桥梁工程知识图谱平台 - FastAPI 主应用
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging
import socket
import sys # For exiting if no port is available
from contextlib import asynccontextmanager

from .core.config import get_settings, create_upload_dir
from .api import documents, knowledge, export
import psutil
import platform

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 获取配置
settings = get_settings()


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"启动 {settings.PROJECT_NAME} v{settings.VERSION}")
    # 创建必要的目录
    create_upload_dir()
    logger.info("应用启动完成 - Lifespan Startup")
    yield
    # Shutdown
    logger.info("应用正在关闭...") # Adjusted to match user's requested log message


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="基于 Graphiti 的桥梁工程知识图谱构建平台",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加信任主机中间件
if not settings.DEBUG:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# 请求处理时间中间件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """添加请求处理时间到响应头"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"全局异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else "请联系管理员"
        }
    )


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": time.time()
    }


# 根路径
@app.get("/")
async def root():
    """根路径信息"""
    return {
        "message": f"欢迎使用 {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs_url": "/docs",
        "api_base": settings.API_V1_STR
    }


# 注册 API 路由
app.include_router(
    documents.router,
    prefix=f"{settings.API_V1_STR}/documents",
    tags=["文档处理"]
)

app.include_router(
    knowledge.router,
    prefix=f"{settings.API_V1_STR}/knowledge",
    tags=["知识图谱"]
)

app.include_router(
    export.router,
    prefix=f"{settings.API_V1_STR}/export",
    tags=["语料导出"]
)


# 应用信息
@app.get(f"{settings.API_V1_STR}/info")
async def get_app_info():
    """获取应用信息"""
    try:
        # 获取系统信息
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "debug": settings.DEBUG,
            "neo4j_uri": settings.NEO4J_URI,
            "ollama_url": settings.OLLAMA_BASE_URL,
            "ollama_llm_model": settings.OLLAMA_LLM_MODEL,
            "ollama_embed_model": settings.OLLAMA_EMBED_MODEL,
            "max_file_size": settings.MAX_FILE_SIZE,
            "allowed_extensions": settings.ALLOWED_EXTENSIONS,
            "system": {
                "cpu_usage": round(cpu_percent, 1),
                "memory_usage": round(memory.percent, 1),
                "disk_usage": round(disk.percent, 1),
                "platform": platform.system(),
                "architecture": platform.machine()
            }
        }
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "debug": settings.DEBUG,
            "system": {
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "platform": "Unknown",
                "architecture": "Unknown"
            }
        }


if __name__ == "__main__":
    import uvicorn

    def find_available_port(host: str, start_port: int, max_attempts: int = 10) -> Optional[int]:
        """Tries to find an available port by binding to it."""
        for port_candidate in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, port_candidate))
                logger.info(f"端口 {port_candidate} 在主机 {host} 上可用.")
                return port_candidate
            except OSError as e:
                logger.warning(f"端口 {port_candidate} 在主机 {host} 上已被占用或发生错误: {e}")
                continue
        return None

    host_to_use = settings.HOST
    # Try default port first, then iterate through a range based on settings.PORT as start
    # The user's example uses a fixed start_port=8000 and max_attempts=10.
    # We can make this configurable via settings if needed, or combine with RETRY_PORTS.
    # For now, let's try the main port, then a sequence.

    port_to_use = None
    # Check initial port from settings
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host_to_use, settings.PORT))
        port_to_use = settings.PORT
        logger.info(f"默认端口 {settings.PORT} 在主机 {host_to_use} 上可用.")
    except OSError:
        logger.warning(f"默认端口 {settings.PORT} 在主机 {host_to_use} 上已被占用. 尝试备用端口...")
        # Define a range for trying alternative ports if default is taken
        # This replaces the direct use of settings.RETRY_PORTS with a range logic
        # Max attempts for finding an alternative if default is taken.
        # Start searching from settings.PORT + 1
        alternative_start_port = settings.PORT + 1
        # Let's use a reasonable number of attempts, e.g., 10, as in user's example.
        # Or, could use len(settings.RETRY_PORTS) if we want to keep that configurable.
        # For simplicity, let's use a fixed number of attempts for alternatives.
        max_alt_attempts = 10
        port_to_use = find_available_port(host_to_use, alternative_start_port, max_alt_attempts)

    if port_to_use is None:
        logger.error(
            f"在主机 {host_to_use} 上无法找到可用端口 (尝试了从 {settings.PORT} 开始的端口). "
            "应用无法启动."
        )
        sys.exit(1)

    logger.info(f"启动 Uvicorn 服务于 {host_to_use}:{port_to_use}")
    uvicorn.run(
        "app.main:app",  # Points to the app instance in the current file
        host=host_to_use,
        port=port_to_use,
        reload=settings.DEBUG,
        log_level="info"
    )