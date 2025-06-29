"""
知识图谱 API 路由
提供知识图谱的搜索、查看、分析等功能
"""
import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.graphiti_service import get_graphiti_service, SearchResult
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


# 请求和响应模型
class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    group_id: Optional[str] = None
    limit: int = 50


@router.post("/search", response_model=SearchResult)
async def search_knowledge_graph(request: SearchRequest):
    """搜索知识图谱"""
    try:
        service = get_graphiti_service()
        
        if service is None:
            return {
                "success": False,
                "error": "Graphiti 服务未初始化",
                "results": []
            }
        
        result = await service.search_knowledge(
            query=request.query,
            limit=request.limit
        )
        
        return result
        
    except Exception as e:
        logger.error(f"知识图谱搜索失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


@router.get("/health")
async def get_knowledge_health():
    """获取知识图谱健康状态"""
    try:
        service = get_graphiti_service()
        
        if service is None:
            return {
                "status": "unhealthy",
                "client_available": False,
                "neo4j_connected": False,
                "message": "Graphiti 服务未初始化"
            }
        
        health_status = service.get_health_status()
        return health_status
        
    except Exception as e:
        logger.error(f"获取知识图谱健康状态失败: {e}")
        return {
            "status": "unhealthy",
            "client_available": False,
            "neo4j_connected": False,
            "message": f"错误: {str(e)}"
        }


@router.get("/stats")
async def get_knowledge_stats():
    """获取知识图谱统计信息"""
    try:
        service = get_graphiti_service()
        
        if service is None:
            return {
                "node_count": 0,
                "edge_count": 0,
                "episode_count": 0,
                "status": "Graphiti 服务未初始化"
            }
        
        stats = await service.get_graph_stats()
        return stats
        
    except Exception as e:
        logger.error(f"获取知识图谱统计失败: {e}")
        return {
            "node_count": 0,
            "edge_count": 0,
            "episode_count": 0,
            "status": f"错误: {str(e)}"
        } 