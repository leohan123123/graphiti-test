"""
桥梁工程知识图谱平台 - 配置管理
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache
import os


class Settings(BaseSettings):
    """应用配置类"""
    
    # 基础配置
    PROJECT_NAME: str = "桥梁工程知识图谱平台"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # 服务器配置
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    # 安全配置
    SECRET_KEY: str = Field(env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    ALGORITHM: str = "HS256"
    
    # Neo4j 配置
    NEO4J_URI: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field(default="neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field(default="bridge123", env="NEO4J_PASSWORD")
    
    # PostgreSQL 配置 (可选 - 本项目主要使用Neo4j)
    POSTGRES_SERVER: str = Field(default="localhost", env="POSTGRES_SERVER")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    POSTGRES_DB: str = Field(default="bridge_knowledge", env="POSTGRES_DB")
    POSTGRES_USER: str = Field(default="postgres", env="POSTGRES_USER")
    POSTGRES_PASSWORD: Optional[str] = Field(default=None, env="POSTGRES_PASSWORD")
    
    @property
    def database_url(self) -> str:
        if self.POSTGRES_PASSWORD:
            return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        return None
    
    # Redis 配置
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # AI 模型配置
    # Ollama 配置
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    OLLAMA_LLM_MODEL: str = Field(default="qwen2.5:7b", env="OLLAMA_LLM_MODEL")
    OLLAMA_EMBED_MODEL: str = Field(default="nomic-embed-text", env="OLLAMA_EMBED_MODEL")
    OLLAMA_EMBED_DIM: int = Field(default=768, env="OLLAMA_EMBED_DIM")
    
    # OpenAI 配置 (可选)
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4", env="OPENAI_MODEL")
    
    # 文件存储配置
    UPLOAD_DIR: str = Field(default="./uploads", env="UPLOAD_DIR")
    MAX_FILE_SIZE: int = Field(default=100_000_000, env="MAX_FILE_SIZE")  # 100MB
    ALLOWED_EXTENSIONS: list = [".pdf", ".docx", ".doc", ".dxf", ".dwg", ".ifc"]
    
    # MinIO 配置 (可选)
    MINIO_ENDPOINT: Optional[str] = Field(default=None, env="MINIO_ENDPOINT")
    MINIO_ACCESS_KEY: Optional[str] = Field(default=None, env="MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY: Optional[str] = Field(default=None, env="MINIO_SECRET_KEY")
    MINIO_BUCKET: str = Field(default="bridge-documents", env="MINIO_BUCKET")
    
    # Graphiti 配置
    GRAPHITI_GROUP_ID: str = Field(default="bridge_engineering", env="GRAPHITI_GROUP_ID")
    
    # 处理配置
    MAX_CONCURRENT_TASKS: int = Field(default=4, env="MAX_CONCURRENT_TASKS")
    TASK_TIMEOUT: int = Field(default=3600, env="TASK_TIMEOUT")  # 1小时
    
    # CORS 配置
    BACKEND_CORS_ORIGINS: list = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="BACKEND_CORS_ORIGINS"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例 (单例模式)"""
    return Settings()


# 创建上传目录
def create_upload_dir():
    """创建上传目录"""
    settings = get_settings()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # 创建子目录
    for subdir in ["pdf", "doc", "cad", "bim", "temp"]:
        os.makedirs(os.path.join(settings.UPLOAD_DIR, subdir), exist_ok=True) 