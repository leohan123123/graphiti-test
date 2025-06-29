"""
语料导出 API 路由
提供知识图谱数据的多格式导出功能，用于LLM训练
"""
import logging
from typing import Optional, List
from pathlib import Path
import csv # For record counting in CSV

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse # Added JSONResponse
from pydantic import BaseModel

from ..services.graphiti_service import get_graphiti_service
# Import the actual service function with a distinct name to avoid confusion
from ..services.graphiti_service import export_knowledge_corpus as service_export_corpus_func
from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


class ExportRequest(BaseModel):
    """导出请求"""
    group_id: Optional[str] = None
    format_type: str = "jsonl"  # Default format

class ExportResponse(BaseModel):
    """导出响应"""
    success: bool
    file_path: str # Relative path for user info
    file_size: int
    record_count: int
    format_type: str
    message: str

class ExportedFileInfo(BaseModel):
    """单个导出文件的信息"""
    filename: str
    size: int
    created_at: float # Timestamp
    download_url: str

class ListExportedFilesResponse(BaseModel):
    """导出文件列表的响应"""
    files: List[ExportedFileInfo]

class DeleteExportResponse(BaseModel):
    """删除导出文件的响应"""
    message: str
    file_name: str


@router.post("/corpus", response_model=ExportResponse)
async def export_knowledge_corpus_post(request: ExportRequest): # Renamed to avoid conflict with import
    """
    导出知识图谱作为训练语料.
    支持的格式: jsonl, txt, csv.
    """
    try:
        graphiti_service = get_graphiti_service()
        if not graphiti_service or not graphiti_service.is_available():
            logger.error("Corpus export failed: Graphiti service is not available.")
            raise HTTPException(status_code=503, detail="知识图谱服务当前不可用，无法导出语料。")

        allowed_formats = ["jsonl", "txt", "csv"]
        if request.format_type.lower() not in allowed_formats:
            logger.warning(f"Invalid export format requested: {request.format_type}")
            raise HTTPException(status_code=400, detail=f"不支持的导出格式: '{request.format_type}'. 支持的格式: {', '.join(allowed_formats)}")
        
        absolute_file_path_str = await service_export_corpus_func(
            group_id=request.group_id,
            format_type=request.format_type
        )
        
        exported_file = Path(absolute_file_path_str)
        if not exported_file.exists() or not exported_file.is_file():
            logger.error(f"Corpus export service call succeeded but file not found at: {absolute_file_path_str}")
            raise HTTPException(status_code=500, detail="导出服务成功执行，但未能找到生成的导出文件。")

        file_size = exported_file.stat().st_size
        record_count = 0
        try:
            if request.format_type == "jsonl" or request.format_type == "txt":
                with open(exported_file, "r", encoding="utf-8") as f:
                    record_count = sum(1 for _ in f)
            elif request.format_type == "csv":
                with open(exported_file, "r", encoding="utf-8", newline='') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header: # Count rows after header
                        record_count = sum(1 for row in reader if any(field.strip() for field in row))
        except Exception as count_exc:
            logger.warning(f"Could not count records in exported file {exported_file.name}: {count_exc}", exc_info=True)

        logger.info(f"Corpus exported successfully: {exported_file.name}, Format: {request.format_type}, Records: {record_count}")
        user_friendly_path = f"exports/{exported_file.name}"
        return ExportResponse(
            success=True,
            file_path=user_friendly_path,
            file_size=file_size,
            record_count=record_count,
            format_type=request.format_type,
            message="语料导出成功"
        )
    except HTTPException as http_exc:
        logger.warning(f"HTTPException during POST /corpus export (format: {request.format_type}): {http_exc.detail}", exc_info=True)
        raise
    except ValueError as ve:
        logger.warning(f"ValueError during POST /corpus export (format: {request.format_type}): {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Unexpected error during POST /corpus export (format: {request.format_type})", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，语料导出失败。")


@router.get("/corpus", response_model=ExportResponse)
async def export_knowledge_corpus_get(
    format_type: str = Query("jsonl", description="导出格式 (jsonl, txt, csv)"),
    group_id: Optional[str] = Query(None, description="分组ID (可选)")
):
    """GET 方式导出语料。"""
    export_req = ExportRequest(group_id=group_id, format_type=format_type)
    # Delegates to the POST endpoint's logic, including its comprehensive error handling.
    return await export_knowledge_corpus_post(request=export_req)


@router.get("/download/{file_name}")
async def download_exported_file(file_name: str):
    """下载导出的文件。文件应位于 'exports' 目录下。"""
    try:
        if not file_name or ".." in file_name or "/" in file_name or "\\" in file_name:
            logger.warning(f"Attempt to download file with invalid or traversal characters in name: {file_name}")
            raise HTTPException(status_code=400, detail="文件名无效或包含禁止字符。")

        exports_base_dir = Path("exports").resolve()
        file_path = (exports_base_dir / file_name).resolve()

        # Security check: Ensure resolved path is still within the intended 'exports' directory
        if not str(file_path).startswith(str(exports_base_dir)):
            logger.error(f"Path traversal attempt detected for download: {file_name} resolved to {file_path}")
            raise HTTPException(status_code=403, detail="禁止访问。")

        if not file_path.exists() or not file_path.is_file():
            logger.warning(f"File not found for download: {file_name} (resolved to {file_path})")
            raise HTTPException(status_code=404, detail="文件不存在或无法访问。")
        
        logger.info(f"Initiating download for exported file: {file_name}")
        return FileResponse(
            path=str(file_path),
            filename=file_name,
            media_type='application/octet-stream' # Generic binary for download
        )
    except HTTPException as http_exc:
        # Re-raise if it's already an HTTPException (e.g., from checks above)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file download for '{file_name}'", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，文件下载失败。")


@router.get("/list", response_model=ListExportedFilesResponse)
async def list_exported_files():
    """列出已导出的文件。"""
    try:
        exports_dir = Path("exports")
        if not exports_dir.exists() or not exports_dir.is_dir():
            logger.info("Exports directory 'exports/' does not exist. Returning empty list.")
            return ListExportedFilesResponse(files=[])

        listed_files: List[ExportedFileInfo] = []
        for item_path in exports_dir.iterdir():
            if item_path.is_file():
                # Basic check for potentially problematic filenames
                if ".." in item_path.name or "/" in item_path.name or "\\" in item_path.name:
                    logger.warning(f"Skipping file with potentially unsafe name in exports list: {item_path.name}")
                    continue
                try:
                    stat = item_path.stat()
                    listed_files.append(ExportedFileInfo(
                        filename=item_path.name,
                        size=stat.st_size,
                        created_at=stat.st_ctime, # Creation time timestamp
                        download_url=f"{settings.API_V1_STR}/export/download/{item_path.name}"
                    ))
                except Exception as stat_exc: # Catch issues like permission errors during stat
                    logger.error(f"Could not stat file {item_path.name} in exports directory: {stat_exc}", exc_info=True)

        logger.info(f"Listed {len(listed_files)} files from exports directory.")
        return ListExportedFilesResponse(files=listed_files)
    except Exception as e:
        logger.error("Unexpected error listing exported files", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，获取导出文件列表失败。")


@router.delete("/{file_name}", response_model=DeleteExportResponse)
async def delete_exported_file(file_name: str):
    """删除指定的导出文件。"""
    try:
        if not file_name or ".." in file_name or "/" in file_name or "\\" in file_name:
            logger.warning(f"Attempt to delete file with invalid or traversal characters in name: {file_name}")
            raise HTTPException(status_code=400, detail="文件名无效或包含禁止字符。")

        exports_base_dir = Path("exports").resolve()
        file_path = (exports_base_dir / file_name).resolve()
        
        # Security check: Ensure resolved path is still within 'exports'
        if not str(file_path).startswith(str(exports_base_dir)):
            logger.error(f"Path traversal attempt detected for delete: {file_name} resolved to {file_path}")
            raise HTTPException(status_code=403, detail="禁止访问。")
        
        if not file_path.exists() or not file_path.is_file():
            logger.warning(f"File not found for deletion: {file_name} (resolved to {file_path})")
            raise HTTPException(status_code=404, detail="要删除的文件不存在。")
        
        file_path.unlink() # Delete the file
        logger.info(f"Successfully deleted exported file: {file_name}")
        
        return DeleteExportResponse(message="文件删除成功", file_name=file_name)
    except HTTPException as http_exc:
        raise
    except OSError as os_err: # Catch file system errors specifically
        logger.error(f"OSError during deletion of file '{file_name}': {os_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除文件时发生文件系统错误。")
    except Exception as e:
        logger.error(f"Unexpected error during deletion of file '{file_name}'", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，删除导出文件失败。")