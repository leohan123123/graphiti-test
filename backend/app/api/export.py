"""
语料导出 API 路由
提供知识图谱数据的多格式导出功能，用于LLM训练
"""
import logging
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..services.graphiti_service import get_graphiti_service
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


class ExportRequest(BaseModel):
    """导出请求"""
    group_id: Optional[str] = None
    format_type: str = "jsonl"  # jsonl, txt, csv


class ExportResponse(BaseModel):
    """导出响应"""
    success: bool
    file_path: str
    file_size: int
    record_count: int
    format_type: str
    message: str


@router.post("/corpus", response_model=ExportResponse)
async def export_knowledge_corpus(request: ExportRequest):
    """
    导出知识图谱作为训练语料
    
    支持的格式：
    - jsonl: JSON Lines 格式，适合大多数 LLM 训练
    - txt: 纯文本格式，适合简单处理
    - csv: CSV 格式，适合表格处理
    """
    try:
        graphiti_service = get_graphiti_service()
        
        # 执行导出
        from ..services.graphiti_service import export_knowledge_corpus
        file_path = await export_knowledge_corpus(
            group_id=request.group_id,
            format_type=request.format_type
        )
        
        # 获取文件信息
        file_size = Path(file_path).stat().st_size
        
        # TODO: 计算记录数量
        record_count = 0  # 简化实现
        
        return ExportResponse(
            success=True,
            file_path=file_path,
            file_size=file_size,
            record_count=record_count,
            format_type=request.format_type,
            message="语料导出成功"
        )
        
    except Exception as e:
        logger.error(f"语料导出失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/corpus")
async def export_knowledge_corpus_get(
    format_type: str = Query("jsonl", description="导出格式"),
    group_id: Optional[str] = Query(None, description="分组ID")
):
    """GET 方式导出语料"""
    request = ExportRequest(group_id=group_id, format_type=format_type)
    return await export_knowledge_corpus(request)


@router.get("/download/{file_name}")
async def download_exported_file(file_name: str):
    """下载导出的文件"""
    try:
        file_path = Path("exports") / file_name
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return FileResponse(
            path=str(file_path),
            filename=file_name,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件下载失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.get("/list")
async def list_exported_files():
    """列出已导出的文件"""
    try:
        exports_dir = Path("exports")
        
        if not exports_dir.exists():
            return {"files": []}
        
        files = []
        for file_path in exports_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "filename": file_path.name,
                    "size": stat.st_size,
                    "created_at": stat.st_ctime,
                    "download_url": f"/api/v1/export/download/{file_path.name}"
                })
        
        return {"files": files}
        
    except Exception as e:
        logger.error(f"获取导出文件列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


@router.delete("/{file_name}")
async def delete_exported_file(file_name: str):
    """删除导出的文件"""
    try:
        file_path = Path("exports") / file_name
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        file_path.unlink()
        
        return {"message": "文件删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除导出文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}") 