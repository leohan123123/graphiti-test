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
        
        if not service or not service.is_available():
            logger.error("Search attempt failed: Graphiti service is not available.")
            raise HTTPException(status_code=503, detail="知识图谱服务当前不可用，请稍后再试。")
        
        # The service.search_knowledge already returns a dict that includes success status and error messages.
        # We should align the SearchResult model or how results are returned.
        # For now, let's assume service.search_knowledge returns a dict like:
        # {"success": True/False, "entities": [], "relationships": [], "total_count": N, "error": "msg"}

        service_result = await service.search_knowledge(
            query=request.query,
            limit=request.limit
        )
        
        if not service_result.get("success"):
            error_detail = service_result.get("error", "知识图谱搜索时发生未知错误。")
            logger.error(f"Knowledge graph search failed with query '{request.query}': {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)

        # If successful, service_result contains entities, relationships, total_count
        return SearchResult(
            entities=service_result.get("entities", []),
            relationships=service_result.get("relationships", []),
            total_count=service_result.get("total_count", 0)
        )
        
    except HTTPException as http_exc:
        # Logged by the service or re-log here if needed, then re-raise
        logger.warning(f"HTTPException during knowledge graph search for query '{request.query}': {http_exc.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during knowledge graph search for query '{request.query}'", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，知识图谱搜索失败。")

# Define a response model for health status for consistency
class KnowledgeHealthResponse(BaseModel):
    status: str
    client_available: bool
    neo4j_connected: bool
    message: str

@router.get("/health", response_model=KnowledgeHealthResponse)
async def get_knowledge_health():
    """获取知识图谱健康状态"""
    try:
        service = get_graphiti_service()
        
        if not service: # service itself could be None if initial global setup failed
            logger.error("Knowledge health check failed: Graphiti service object is None.")
            # Return a valid KnowledgeHealthResponse indicating unavailability
            return KnowledgeHealthResponse(
                status="unhealthy",
                client_available=False,
                neo4j_connected=False,
                message="Graphiti 服务未初始化或初始化失败。"
            )
        
        # get_health_status should ideally return a dict that matches KnowledgeHealthResponse
        health_status_dict = service.get_health_status()
        return KnowledgeHealthResponse(**health_status_dict)
        
    except Exception as e:
        logger.error("Unexpected error fetching knowledge graph health status", exc_info=True)
        # In case of truly unexpected error, return 500 or a default unhealthy status
        # Raising HTTPException might be better to signal a server fault rather than a service health issue
        raise HTTPException(status_code=500, detail="服务器内部错误，无法获取知识图谱健康状态。")

# Define a response model for stats
class KnowledgeStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    episode_count: int # Assuming this is part of stats from graphiti_service
    status: str # e.g., "ok", "unavailable", "error"

@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats():
    """获取知识图谱统计信息"""
    try:
        service = get_graphiti_service()
        
        if not service or not service.is_available():
            logger.error("Knowledge stats request failed: Graphiti service is not available.")
            # Return a valid KnowledgeStatsResponse indicating unavailability
            return KnowledgeStatsResponse(
                node_count=0,
                edge_count=0,
                episode_count=0,
                status="知识图谱服务当前不可用"
            )
        
        stats_dict = await service.get_graph_stats()
        # Ensure stats_dict matches KnowledgeStatsResponse fields
        return KnowledgeStatsResponse(**stats_dict)
        
    except Exception as e:
        logger.error("Unexpected error fetching knowledge graph statistics", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，无法获取知识图谱统计信息。")