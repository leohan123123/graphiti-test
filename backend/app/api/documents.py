"""
文档处理 API 路由
提供 PDF、Word、CAD、BIM 文件的上传和解析功能
"""
import os
import json
import aiofiles
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.config import get_settings
from ..utils.pdf_parser import parse_pdf_file, PDFContent
from ..services.graphiti_service import get_graphiti_service, KnowledgeGraphResult

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# 文档数据存储文件路径
DOCUMENTS_DB_PATH = os.path.join(settings.UPLOAD_DIR, "documents_db.json")

# 响应模型
class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool
    file_id: str
    filename: str
    file_size: int
    file_type: str
    message: str


class DocumentParseResponse(BaseModel):
    """文档解析响应"""
    success: bool
    file_id: str
    content: PDFContent
    processing_time: float
    message: str


class ProcessingStatus(BaseModel):
    """处理状态"""
    file_id: str
    status: str  # uploading, parsing, building_graph, completed, error
    progress: int  # 0-100
    message: str
    result: Dict[str, Any] = {}


class DocumentInfo(BaseModel):
    """文档信息"""
    file_id: str
    filename: str
    file_type: str
    file_size: int
    upload_time: datetime
    status: str = "uploaded"
    processed_at: Optional[datetime] = None
    node_count: int = 0
    error_message: Optional[str] = None


def load_documents_db() -> Dict[str, DocumentInfo]:
    """加载文档数据库"""
    try:
        if os.path.exists(DOCUMENTS_DB_PATH):
            with open(DOCUMENTS_DB_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 转换为DocumentInfo对象
                documents = {}
                for file_id, doc_data in data.items():
                    # 处理datetime字段
                    if doc_data.get('upload_time') and isinstance(doc_data['upload_time'], str):
                        doc_data['upload_time'] = datetime.fromisoformat(doc_data['upload_time'].replace('Z', '+00:00'))
                    if doc_data.get('processed_at') and isinstance(doc_data['processed_at'], str):
                        doc_data['processed_at'] = datetime.fromisoformat(doc_data['processed_at'].replace('Z', '+00:00'))
                    
                    documents[file_id] = DocumentInfo(**doc_data)
                return documents
        return {}
    except Exception as e:
        logger.error(f"加载文档数据库失败: {e}")
        return {}


def save_documents_db(documents: Dict[str, DocumentInfo]):
    """保存文档数据库"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(DOCUMENTS_DB_PATH), exist_ok=True)
        
        # 转换为可序列化的字典
        data = {}
        for file_id, doc_info in documents.items():
            doc_dict = doc_info.model_dump()
            # 转换datetime为ISO字符串
            if doc_dict.get('upload_time'):
                doc_dict['upload_time'] = doc_dict['upload_time'].isoformat()
            if doc_dict.get('processed_at'):
                doc_dict['processed_at'] = doc_dict['processed_at'].isoformat()
            data[file_id] = doc_dict
        
        with open(DOCUMENTS_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存文档数据库失败: {e}")


def get_document_info(file_id: str) -> DocumentInfo:
    """获取文档信息"""
    documents = load_documents_db()
    return documents.get(file_id)


def update_document_status(file_id: str, status: str, **kwargs):
    """更新文档状态"""
    documents = load_documents_db()
    if file_id in documents:
        documents[file_id].status = status
        for key, value in kwargs.items():
            if hasattr(documents[file_id], key):
                setattr(documents[file_id], key, value)
        save_documents_db(documents)


# 全局状态存储 (简化实现，生产环境应使用 Redis 或数据库)
processing_status: Dict[str, ProcessingStatus] = {}


def validate_file(file: UploadFile) -> None:
    """验证上传的文件"""
    # 检查文件大小
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制 ({settings.MAX_FILE_SIZE / 1024 / 1024:.1f}MB)"
        )
    
    # 检查文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )


def get_file_type(filename: str) -> str:
    """根据文件名获取文件类型"""
    ext = Path(filename).suffix.lower()
    
    type_map = {
        '.pdf': 'pdf',
        '.doc': 'doc',
        '.docx': 'doc', 
        '.dxf': 'cad',
        '.dwg': 'cad',
        '.ifc': 'bim'
    }
    
    return type_map.get(ext, 'unknown')


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    上传文件
    
    支持的文件类型：
    - PDF: .pdf
    - Word: .doc, .docx
    - CAD: .dxf, .dwg
    - BIM: .ifc
    """
    try:
        # 验证文件
        validate_file(file)
        
        # 生成文件ID
        import uuid
        file_id = str(uuid.uuid4())
        
        # 确定文件类型和存储路径
        file_type = get_file_type(file.filename)
        storage_dir = os.path.join(settings.UPLOAD_DIR, file_type)
        os.makedirs(storage_dir, exist_ok=True)
        
        # 生成安全的文件名
        safe_filename = f"{file_id}_{file.filename}"
        file_path = os.path.join(storage_dir, safe_filename)
        
        # 保存文件
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # 创建文档信息并保存到持久化存储
        doc_info = DocumentInfo(
            file_id=file_id,
            filename=file.filename,
            file_type=file_type,
            file_size=len(content),
            upload_time=datetime.now(),
            status="uploaded"
        )
        
        # 保存到持久化数据库
        documents = load_documents_db()
        documents[file_id] = doc_info
        save_documents_db(documents)
        
        # 记录处理状态
        processing_status[file_id] = ProcessingStatus(
            file_id=file_id,
            status="uploaded",
            progress=100,
            message="文件上传成功"
        )
        
        logger.info(f"文件上传成功: {file.filename} -> {file_path}")
        
        return FileUploadResponse(
            success=True,
            file_id=file_id,
            filename=file.filename,
            file_size=len(content),
            file_type=file_type,
            message="文件上传成功"
        )
        
    except HTTPException as http_exc:
        logger.warning(f"HTTPException during file upload for '{file.filename}': {http_exc.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file upload for '{file.filename}'", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，文件上传失败。请稍后重试或联系管理员。")


def find_file_by_id(file_id: str) -> tuple[str, str] | None:
    """根据文件ID查找文件路径和原始文件名"""
    for subdir in ["pdf", "doc", "cad", "bim"]:
        search_dir = os.path.join(settings.UPLOAD_DIR, subdir)
        if os.path.exists(search_dir):
            for f in os.listdir(search_dir):
                if f.startswith(file_id + "_"):
                    file_path = os.path.join(search_dir, f)
                    filename = f[len(file_id) + 1:]  # 移除 file_id 前缀
                    return file_path, filename
    return None


@router.get("/status/{file_id}", response_model=ProcessingStatus)
async def get_processing_status(file_id: str):
    """获取文件处理状态"""
    try:
        documents = load_documents_db()
        if file_id not in documents:
            logger.warning(f"Status requested for non-existent file_id: {file_id}")
            raise HTTPException(status_code=404, detail="文件ID不存在")

        doc_info = documents[file_id]

        # 根据文档状态计算进度和消息
    progress_map = {
        "uploaded": 0,
        "processing": 50,
        "completed": 100,
        "failed": 100
    }
    
    message_map = {
        "uploaded": "文件已上传，等待处理",
        "processing": "正在处理文档...",
        "completed": "文档处理完成",
        "failed": f"处理失败: {doc_info.error_message or '未知错误'}"
    }
    
    return ProcessingStatus(
        file_id=file_id,
        status=doc_info.status,
        progress=progress_map.get(doc_info.status, 0),
        message=message_map.get(doc_info.status, "未知状态"),
        result={
            "node_count": doc_info.node_count,
            "processed_at": doc_info.processed_at.isoformat() if doc_info.processed_at else None,
            "error_message": doc_info.error_message
        }
    )
    except HTTPException as http_exc:
        # This will be caught by the global exception handler if not handled here,
        # but explicit logging can be useful.
        logger.warning(f"HTTPException in get_processing_status for file_id '{file_id}': {http_exc.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_processing_status for file_id '{file_id}'", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，获取状态失败。")


async def _parse_document_internal(file_id: str, enable_ocr: bool = True):
    """内部解析函数，返回原始数据而不是JSONResponse"""
    # This is an internal helper, so direct exception handling might be less critical
    # if the calling function handles them. However, adding some for robustness.
    try:
        # 检查文件ID，如果内存中没有则尝试恢复
        if file_id not in processing_status:
            file_info_tuple = find_file_by_id(file_id) # Renamed to avoid conflict
            if file_info_tuple is None:
                logger.error(f"File ID {file_id} not found by find_file_by_id in _parse_document_internal.")
                raise HTTPException(status_code=404, detail="文件ID不存在 (internal find failed)")
            
            # 重建处理状态
            file_path, filename = file_info_tuple
            processing_status[file_id] = ProcessingStatus(
                file_id=file_id,
                status="uploaded", # Or "unknown_recovered"
                progress=0, # Reset progress
                message="文件状态已恢复（可能在服务重启后）"
            )
        
        # 更新状态
        processing_status[file_id].status = "parsing"
        processing_status[file_id].progress = 10
        processing_status[file_id].message = "正在解析文档..."
        
        # 查找文件
        file_info_tuple_lookup = find_file_by_id(file_id) # Renamed
        if file_info_tuple_lookup is None:
            processing_status[file_id].status = "error"
            processing_status[file_id].message = "文件物理路径未找到"
            logger.error(f"Physical file for ID {file_id} not found during parsing attempt.")
            raise HTTPException(status_code=404, detail="文件物理路径未找到")
        
        file_path, filename = file_info_tuple_lookup
        
        # 更新进度
        processing_status[file_id].progress = 30
        
        # 根据文件类型解析
        file_type = get_file_type(filename)
        
        if file_type == "pdf":
            from ..utils.pdf_parser import parse_pdf_file
            
            # 解析PDF文件
            pdf_content = parse_pdf_file(file_path, enable_ocr=enable_ocr)
            
            # 转换为JSON可序列化的格式
            def ultra_clean_string(s):
                if not isinstance(s, str):
                    return str(s) if s is not None else ""

                cleaned = ""
                for char in s:
                    code = ord(char)
                    # Allow basic printable ASCII, common whitespace, and CJK Unified Ideographs
                    if (32 <= code <= 126) or char in '\n\r\t' or \
                       (0x4e00 <= code <= 0x9fff) or \
                       (0x3000 <= code <= 0x303f) or \
                       (0xff00 <= code <= 0xffef): # Added CJK Symbols/Punctuation and Fullwidth forms
                        cleaned += char
                    elif code > 127: # Keep other Unicode characters too for now
                        cleaned += char
                return cleaned.strip()

            def deep_clean_data(obj):
                if isinstance(obj, dict):
                    return {ultra_clean_string(str(k)): deep_clean_data(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [deep_clean_data(item) for item in obj]
                elif isinstance(obj, str):
                    return ultra_clean_string(obj)
                else:
                    return obj # Keep non-string, non-dict, non-list as is

            content_dict = {
                "text": ultra_clean_string(pdf_content.text),
                "page_count": pdf_content.page_count,
                "metadata": deep_clean_data(pdf_content.metadata),
                "images": deep_clean_data(pdf_content.images), # Images list might contain complex objects
                "has_forms": pdf_content.has_forms,
                "tables": deep_clean_data(pdf_content.tables) # Tables list
            }
            
            # 更新状态
            # This status update should ideally be in the calling function after success
            # processing_status[file_id].status = "completed"
            # processing_status[file_id].progress = 100
            # processing_status[file_id].message = "文档解析完成"
            # processing_status[file_id].result = {
            #     "content": content_dict,
            #     "processing_time": 0.0
            # }

            return {
                "success": True,
                "file_id": file_id,
                "content": content_dict, # This is the PDFContent model data, not yet JSON
                "message": "PDF 解析完成"
            }
            
        else:
            logger.warning(f"Unsupported file type '{file_type}' for parsing in _parse_document_internal for file_id '{file_id}'.")
            raise HTTPException(
                status_code=400, 
                detail=f"暂不支持 {file_type} 文件类型的解析"
            )
    except HTTPException as http_exc:
        logger.error(f"HTTPException in _parse_document_internal for {file_id}: {http_exc.detail}", exc_info=True)
        if file_id in processing_status:
            processing_status[file_id].status = "error"
            processing_status[file_id].message = f"内部解析错误: {http_exc.detail}"
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _parse_document_internal for {file_id}", exc_info=True)
        if file_id in processing_status:
            processing_status[file_id].status = "error"
            processing_status[file_id].message = f"内部解析意外失败: {str(e)}"
        # Re-raise as a generic 500 if it's not an HTTPException already
        raise HTTPException(status_code=500, detail=f"内部解析意外失败: {str(e)}")


@router.post("/parse/{file_id}")
async def parse_document(file_id: str, enable_ocr: bool = True):
    """
    解析文档内容

    目前支持 PDF 文档解析，后续会扩展支持其他格式
    """
    start_time = datetime.now()
    try:
        # Initial status check and setup (simplified from original as _parse_document_internal handles some of this)
        doc_info_db = get_document_info(file_id)
        if not doc_info_db:
            logger.warning(f"Parse requested for non-existent file_id in DB: {file_id}")
            raise HTTPException(status_code=404, detail="文件ID在数据库中不存在")

        if file_id not in processing_status:
             processing_status[file_id] = ProcessingStatus(
                file_id=file_id, status="pending_parse", progress=0, message="解析任务已创建"
            )

        processing_status[file_id].status = "parsing"
        processing_status[file_id].progress = 10
        processing_status[file_id].message = "正在解析文档..."

        # Call internal parsing logic
        parsed_data = await _parse_document_internal(file_id, enable_ocr)

        processing_time_seconds = (datetime.now() - start_time).total_seconds()
        
        # Update status upon successful parsing
        processing_status[file_id].status = "parsed_successfully" # More specific status
        processing_status[file_id].progress = 100
        processing_status[file_id].message = "文档解析成功完成"
        # parsed_data["content"] is already a dict from _parse_document_internal
        processing_status[file_id].result = {
            "content_summary": {
                "page_count": parsed_data["content"]["page_count"],
                "text_length": len(parsed_data["content"]["text"]),
                "num_images": len(parsed_data["content"]["images"]),
                "num_tables": len(parsed_data["content"]["tables"]),
            },
            "processing_time": processing_time_seconds
        }

        # Update DB status
        update_document_status(file_id, "parsed_successfully", processed_at=datetime.now())

        # Return the actual parsed content along with success metrics
        # The PDFContent model fields might not be directly serializable by Pydantic if they contain complex types
        # _parse_document_internal now returns a dict, so this should be fine.
        final_response_content = {
            "success": True,
            "file_id": file_id,
            "content": parsed_data["content"], # This is the cleaned dict
            "processing_time": processing_time_seconds,
            "message": "文档解析成功完成"
        }
        return JSONResponse(content=final_response_content) # Ensure it's JSON serializable

    except HTTPException as http_exc:
        logger.warning(f"HTTPException during parsing for file_id '{file_id}': {http_exc.detail}")
        if file_id in processing_status:
            processing_status[file_id].status = "error_parsing"
            processing_status[file_id].message = f"文档解析失败: {http_exc.detail}"
        update_document_status(file_id, "error_parsing", error_message=http_exc.detail)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during parsing for file_id '{file_id}'", exc_info=True)
        if file_id in processing_status:
            processing_status[file_id].status = "error_parsing"
            processing_status[file_id].message = f"文档解析意外失败: {str(e)}"
        update_document_status(file_id, "error_parsing", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"服务器内部错误，文档解析失败。")


async def build_knowledge_graph_background(file_id: str, pdf_content_dict: Dict[str, Any], filename: str):
    """后台任务：构建知识图谱. Takes dict instead of PDFContent model."""
    try:
        # Ensure status exists for file_id
        if file_id not in processing_status:
            processing_status[file_id] = ProcessingStatus(
                file_id=file_id, status="unknown", progress=0, message="BG task started for unknown file"
            )

        processing_status[file_id].status = "building_graph"
        processing_status[file_id].progress = 50 # Arbitrary progress for KG build start
        processing_status[file_id].message = "正在构建知识图谱..."
        update_document_status(file_id, "building_graph")
        
        graphiti_service = get_graphiti_service()
        if not graphiti_service or not graphiti_service.is_available():
            logger.error(f"Graphiti service not available for KG build for file_id {file_id}.")
            raise Exception("Graphiti服务不可用或未初始化")

        # Reconstruct PDFContent from dict for graphiti_service if it expects the model
        # For now, graphiti_service.build_knowledge_graph_from_pdf expects PDFContent model
        # but build_knowledge_graph expects text. We need to align this.
        # The current `build_knowledge_graph_from_pdf` in graphiti_service.py takes text chunks.
        # Let's assume for now the background task gets the text directly.
        # The `process_pdf_document` calls `graphiti_service.build_knowledge_graph` with text.
        # This `build_knowledge_graph_background` seems to be part of an older flow or needs text.
        # Re-aligning: this function should receive text, not a PDFContent object/dict.
        # However, the caller `process_document_background` -> `process_pdf_document` calls
        # `graphiti_service.build_knowledge_graph(text=pdf_content.text, ...)`
        # So this `build_knowledge_graph_background` might be unused or needs refactoring.
        # For now, let's assume it gets the text it needs from `pdf_content_dict['text']`.

        text_to_process = pdf_content_dict.get("text")
        if not text_to_process:
            logger.error(f"No text found in pdf_content_dict for KG build of {file_id}")
            raise ValueError("Text content is missing for knowledge graph construction.")

        # This call is problematic as build_knowledge_graph_from_pdf expects PDFContent model
        # and build_knowledge_graph expects just text.
        # Let's use the direct text method:
        result_dict = await graphiti_service.build_knowledge_graph(
            text=text_to_process, # Pass the text
            document_id=file_id # document_id is used as episode_name prefix
        )
        
        # Convert result (which is a dict) to KnowledgeGraphResult if needed, or handle dict directly
        # The current result_dict is already a dict with success, counts, etc.
        
        current_time = datetime.now()
        if result_dict.get("success"):
            processing_status[file_id].status = "completed"
            processing_status[file_id].message = "知识图谱构建完成"
            node_count = result_dict.get("actual_created_entities", 0) # Or total_graph_nodes
            update_document_status(file_id, "completed", processed_at=current_time, node_count=node_count, error_message=None)
            logger.info(f"✅ 文档 {filename} (ID: {file_id}) 知识图谱构建完成，节点数: {node_count}")
        else:
            error_msg = result_dict.get("error", "知识图谱构建未知错误")
            processing_status[file_id].status = "error_kg_build"
            processing_status[file_id].message = f"知识图谱构建失败: {error_msg}"
            update_document_status(file_id, "error_kg_build", processed_at=current_time, error_message=error_msg)
            logger.error(f"❌ 文档 {filename} (ID: {file_id}) 知识图谱构建失败: {error_msg}")

        processing_status[file_id].progress = 100
        # processing_status[file_id].result.update({"knowledge_graph": result_dict}) # Store full result if needed
        
    except Exception as e:
        logger.error(f"知识图谱后台构建失败 for file_id {file_id}: {str(e)}", exc_info=True)
        if file_id in processing_status: # Check again in case it was cleared
            processing_status[file_id].status = "error_kg_build"
            processing_status[file_id].message = f"知识图谱构建异常: {str(e)}"
        update_document_status(file_id, "error_kg_build", processed_at=datetime.now(), error_message=str(e))


@router.post("/process/{file_id}")
async def process_document(
    file_id: str,
    background_tasks: BackgroundTasks
):
    """处理单个文档"""
    try:
        # 检查文档是否存在
        docs_db = load_documents_db()
        if file_id not in docs_db:
            raise HTTPException(status_code=404, detail="文档不存在")
        
        doc_info = docs_db[file_id]
        
        # 检查是否已经在处理中
        if doc_info.status == "processing":
            return {"message": "文档正在处理中", "status": "processing"}
        
        # 更新状态为处理中
        doc_info.status = "processing"
        doc_info.processed_at = datetime.now()
        docs_db[file_id] = doc_info
        save_documents_db(docs_db)
        
        logger.info(f"🚀 开始处理文档: {doc_info.filename} (ID: {file_id})")
        
        # 启动后台处理任务 - 传递字典格式
        doc_dict = {
            "filename": doc_info.filename,
            "file_type": doc_info.file_type,
            "file_size": doc_info.file_size,
            "upload_time": doc_info.upload_time,
            "status": doc_info.status,
            "processed_at": doc_info.processed_at,
            "node_count": doc_info.node_count,
            "error_message": doc_info.error_message
        }
        background_tasks.add_task(process_document_background, file_id, doc_dict)
        
        return {
            "message": "文档处理已开始",
            "file_id": file_id,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"❌ 处理文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_document_background(file_id: str, doc_info: Dict[str, Any]):
    """后台处理文档的任务"""
    try:
        logger.info(f"📄 开始后台处理文档: {doc_info['filename']}")
        
        # 构建文件路径 - 使用find_file_by_id函数
        file_info = find_file_by_id(file_id)
        if file_info is None:
            logger.error(f"❌ 文件不存在，file_id: {file_id}")
            # 更新状态为失败
            docs_db = load_documents_db()
            if file_id in docs_db:
                doc_info = docs_db[file_id]
                doc_info.status = "failed"
                doc_info.error_message = "文件不存在"
                docs_db[file_id] = doc_info
                save_documents_db(docs_db)
            return
        
        file_path, original_filename = file_info
        
        # 根据文件类型处理
        if doc_info["file_type"] == "pdf":
            await process_pdf_document(file_id, file_path, doc_info)
        elif doc_info["file_type"] in ["cad", "bim"]:
            await process_cad_bim_document(file_id, file_path, doc_info)
        else:
            logger.warning(f"⚠️ 不支持的文件类型: {doc_info['file_type']}")
            # 更新状态为不支持
            docs_db = load_documents_db()
            if file_id in docs_db:
                doc_info_obj = docs_db[file_id]
                doc_info_obj.status = "failed"
                doc_info_obj.error_message = f"不支持的文件类型: {doc_info['file_type']}"
                docs_db[file_id] = doc_info_obj
                save_documents_db(docs_db)
            
    except Exception as e:
        logger.error(f"❌ 后台处理文档失败: {e}")
        # 更新状态为失败
        docs_db = load_documents_db()
        if file_id in docs_db:
            doc_info = docs_db[file_id]
            doc_info.status = "failed"
            doc_info.error_message = str(e)
            docs_db[file_id] = doc_info
            save_documents_db(docs_db)

async def process_pdf_document(file_id: str, file_path: str, doc_info: Dict[str, Any]):
    """处理PDF文档"""
    try:
        logger.info(f"📖 解析PDF文档: {doc_info['filename']}")
        
        # 解析PDF
        from ..utils.pdf_parser import parse_pdf_file
        pdf_content = parse_pdf_file(file_path, enable_ocr=True)
        
        if not pdf_content or not pdf_content.text.strip():
            logger.warning(f"⚠️ PDF文档无文本内容: {doc_info['filename']}")
            # 更新状态为完成但无内容
            docs_db = load_documents_db()
            doc_info = docs_db[file_id]
            doc_info.status = "completed"
            doc_info.node_count = 0
            doc_info.error_message = "文档无文本内容"
            docs_db[file_id] = doc_info
            save_documents_db(docs_db)
            return
        
        logger.info(f"✅ PDF解析完成，文本长度: {len(pdf_content.text)} 字符")
        
        # 构建知识图谱
        logger.info(f"🕸️ 开始构建知识图谱...")
        
        from ..services.graphiti_service import get_graphiti_service
        
        # 使用新的Graphiti服务
        graphiti_service = get_graphiti_service()
        if graphiti_service is None:
            raise Exception("Graphiti服务未初始化")
            
        result = await graphiti_service.build_knowledge_graph(
            text=pdf_content.text,
            document_id=file_id
        )
        
        # 更新文档状态
        docs_db = load_documents_db()
        doc_info = docs_db[file_id]
        doc_info.status = "completed"
        doc_info.processed_at = datetime.now()
        doc_info.node_count = result.get("node_count", 0)
        
        if not result.get("success"):
            doc_info.error_message = result.get("error", "知识图谱构建失败")
            logger.error(f"❌ 知识图谱构建失败: {result.get('error')}")
        else:
            logger.info(f"✅ 知识图谱构建成功，节点数: {result.get('node_count', 0)}")
        
        docs_db[file_id] = doc_info
        save_documents_db(docs_db)
        
    except Exception as e:
        logger.error(f"❌ PDF文档处理失败: {e}")
        # 更新状态为失败
        docs_db = load_documents_db()
        if file_id in docs_db:
            doc_info = docs_db[file_id]
            doc_info.status = "failed"
            doc_info.error_message = str(e)
            docs_db[file_id] = doc_info
            save_documents_db(docs_db)

async def process_cad_bim_document(file_id: str, file_path: str, doc_info: Dict[str, Any]):
    """处理CAD/BIM文档"""
    try:
        logger.info(f"🏗️ 处理CAD/BIM文档: {doc_info['filename']}")
        
        # TODO: 实现CAD/BIM文件解析
        # 目前暂时标记为不支持
        
        docs_db = load_documents_db()
        doc_info = docs_db[file_id]
        doc_info.status = "completed"
        doc_info.processed_at = datetime.now()
        doc_info.node_count = 0
        doc_info.error_message = "CAD/BIM文件处理功能待实现"
        docs_db[file_id] = doc_info
        save_documents_db(docs_db)
        
        logger.info(f"⚠️ CAD/BIM文档处理完成（功能待实现）")
        
    except Exception as e:
        logger.error(f"❌ CAD/BIM文档处理失败: {e}")
        # 更新状态为失败
        docs_db = load_documents_db()
        if file_id in docs_db:
            doc_info = docs_db[file_id]
            doc_info.status = "failed"
            doc_info.error_message = str(e)
            docs_db[file_id] = doc_info
            save_documents_db(docs_db)


@router.get("/list")
async def list_uploaded_files():
    """列出已上传的文件"""
    try:
        # 从持久化存储中读取文档信息
        documents = load_documents_db()
        files = []
        
        for file_id, doc_info in documents.items():
            # 获取当前处理状态
            current_status = doc_info.status
            if file_id in processing_status:
                current_status = processing_status[file_id].status
            
            # 转换为API响应格式
            file_data = {
                "file_id": file_id,
                "filename": doc_info.filename,
                "file_type": doc_info.file_type,
                "file_size": doc_info.file_size,
                "upload_time": doc_info.upload_time.timestamp() if isinstance(doc_info.upload_time, datetime) else doc_info.upload_time,
                "status": current_status,
                "node_count": doc_info.node_count,
                "processed_at": doc_info.processed_at.timestamp() if doc_info.processed_at and isinstance(doc_info.processed_at, datetime) else None,
                "error_message": doc_info.error_message
            }
            
            files.append(file_data)
        
        # 按上传时间倒序排列
        files.sort(key=lambda x: x["upload_time"], reverse=True)
        
        return {"files": files}
        
    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """删除文件"""
    try:
        # 检查文件是否存在于持久化存储中
        documents = load_documents_db()
        if file_id not in documents:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        deleted = False
        
        # 在各个目录中查找并删除文件
        for subdir in ["pdf", "doc", "cad", "bim", "temp"]:
            dir_path = os.path.join(settings.UPLOAD_DIR, subdir)
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.startswith(file_id):
                        file_path = os.path.join(dir_path, filename)
                        os.remove(file_path)
                        deleted = True
                        logger.info(f"删除文件: {file_path}")
        
        # 从持久化存储中删除文档信息
        del documents[file_id]
        save_documents_db(documents)
        
        # 删除处理状态
        if file_id in processing_status:
            del processing_status[file_id]
        
        return {"message": "文件删除成功"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")


@router.get("/stats")
async def get_document_stats():
    """获取文档统计信息 - 真实数据"""
    try:
        documents = load_documents_db()
        
        total_documents = len(documents)
        # Refined status checking for more accuracy
        processed_documents = len([doc for doc in documents.values() if doc.status == "completed"])
        processing_documents = len([doc for doc in documents.values() if doc.status in ["processing", "parsing", "building_graph", "processing_queued"]])
        # Consider various failure states
        failed_documents = len([doc for doc in documents.values() if "fail" in doc.status or "error" in doc.status])
        
        total_nodes = sum(doc.node_count for doc in documents.values() if isinstance(doc.node_count, int))
        
        file_types_counts = {}
        for doc in documents.values():
            file_types_counts[doc.file_type] = file_types_counts.get(doc.file_type, 0) + 1
        
        total_size_bytes_val = sum(doc.file_size for doc in documents.values() if isinstance(doc.file_size, int))
        
        # Placeholder for relations, actual count should come from graph_stats if available
        # This is a very rough estimate and might be misleading.
        # Consider linking this to graphiti_service.get_graph_stats() if a global stat is needed.
        estimated_total_relations = total_nodes * 2

        return {
            "total_documents": total_documents,
            "processed_documents": processed_documents,
            "processing_documents": processing_documents,
            "failed_documents": failed_documents,
            "total_extracted_nodes": total_nodes, # Renamed for clarity
            "estimated_total_relations": estimated_total_relations,
            "file_types": file_types_counts,
            "total_size_bytes": total_size_bytes_val,
            "total_size_mb": round(total_size_bytes_val / (1024 * 1024), 2) if total_size_bytes_val else 0.0
        }
    except Exception as e:
        logger.error("获取文档统计信息失败", exc_info=True)
        # Return a more structured error response or raise HTTPException
        # For now, returning empty/zeroed stats as per original logic, but this could be an HTTPException too.
        # raise HTTPException(status_code=500, detail="服务器内部错误，获取文档统计信息失败。")
        # Keeping original return type for now:
        return {
            "total_documents": 0, "processed_documents": 0, "processing_documents": 0,
            "failed_documents": 0, "total_extracted_nodes": 0, "estimated_total_relations": 0,
            "file_types": {}, "total_size_bytes": 0, "total_size_mb": 0.0,
            "error": "Failed to retrieve statistics." # Added error field
        }