"""
桥梁工程知识图谱服务
基于 Graphiti 框架实现知识图谱构建和管理
"""
import os
import logging
import asyncio
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel
from pathlib import Path

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from ..core.config import get_settings
from ..utils.pdf_parser import PDFContent

logger = logging.getLogger(__name__)

class KnowledgeGraphResult(BaseModel):
    """知识图谱构建结果"""
    success: bool
    entity_count: int
    relationship_count: int
    processing_time: float
    group_id: str
    error_message: Optional[str] = None

class SearchResult(BaseModel):
    """搜索结果"""
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    total_count: int

class GraphitiService:
    """Graphiti 知识图谱服务"""
    
    def __init__(self):
        self.client: Optional[Graphiti] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化 Graphiti 客户端"""
        try:
            logger.info("🔧 正在初始化 Graphiti 客户端...")
            
            # 方式1：使用DeepSeek API（优先）
            try:
                from graphiti_core.llm_client.config import LLMConfig
                from app.services.deepseek_client import DeepSeekClient
                from app.services.deepseek_embedder import DeepSeekEmbedder
                
                # 配置 DeepSeek LLM（使用自定义客户端）
                llm_config = LLMConfig(
                    api_key="sk-0b26cde0319b451e984c38a0734353e7",
                    model="deepseek-chat",
                    base_url="https://api.deepseek.com/v1"
                )
                llm_client = DeepSeekClient(config=llm_config)
                
                # 使用自定义嵌入器，避免调用OpenAI API
                embedder = DeepSeekEmbedder()
                
                # 配置Graphiti，使用DeepSeek LLM和自定义嵌入器
                self.client = Graphiti(
                    uri="bolt://localhost:7687",
                    user="neo4j", 
                    password="bridge123",
                    llm_client=llm_client,
                    embedder=embedder
                    # cross_encoder=None (默认，避免额外API调用)
                )
                logger.info("✅ Graphiti 客户端初始化成功（使用DeepSeek API）")
                return
            except Exception as e1:
                logger.warning(f"⚠️ DeepSeek初始化失败: {e1}")
            
            # 方式2：使用环境变量中的OpenAI配置（备用）
            if os.environ.get("OPENAI_API_KEY"):
                try:
                    self.client = Graphiti(
                        uri="bolt://localhost:7687",
                        user="neo4j", 
                        password="bridge123"
                    )
                    logger.info("✅ Graphiti 客户端初始化成功（使用OpenAI配置）")
                    return
                except Exception as e2:
                    logger.warning(f"⚠️ OpenAI初始化失败: {e2}")
            
            # 方式3：最简单的初始化（最后备用）
            try:
                self.client = Graphiti(
                    uri="bolt://localhost:7687",
                    user="neo4j", 
                    password="bridge123"
                )
                logger.info("✅ Graphiti 客户端初始化成功（使用默认配置）")
                return
            except Exception as e3:
                logger.warning(f"⚠️ 默认初始化失败: {e3}")
            
            raise Exception("所有初始化方式都失败了")
            
        except Exception as e:
            logger.error(f"❌ Graphiti 客户端初始化失败: {e}")
            self.client = None


    def is_available(self) -> bool:
        """检查 Graphiti 是否可用"""
        return self.client is not None
    
    async def build_knowledge_graph(self, text: str, document_id: str) -> Dict[str, Any]:
        """构建知识图谱"""
        if not self.is_available():
            logger.error("❌ Graphiti 客户端不可用")
            return {
                "success": False,
                "error": "Graphiti 客户端不可用",
                "node_count": 0,
                "edge_count": 0
            }
        
        try:
            logger.info(f"🚀 开始为文档 {document_id} 构建知识图谱...")
            logger.info(f"📄 文本长度: {len(text)} 字符")
            
            # 添加文档到知识图谱
            episode_name = f"document_{document_id}"
            
            # 使用 Graphiti 添加文档
            logger.info("📝 正在添加文档到知识图谱...")
            
            # 调用 Graphiti 的 add_episode 方法
            episode_result = await self.client.add_episode(
                name=episode_name,
                episode_body=text,
                source_description="桥梁工程技术文档",
                reference_time=datetime.now(),
                source=EpisodeType.text  # 使用文本类型
                
            )
            
            logger.info(f"✅ 文档添加成功: {episode_result}")
            
            # 获取统计信息
            stats = await self.get_graph_stats()
            
            logger.info(f"📊 知识图谱统计: 节点数={stats.get('node_count', 0)}, 边数={stats.get('edge_count', 0)}")
            
            return {
                "success": True,
                "episode_name": episode_name,
                "node_count": stats.get('node_count', 0),
                "edge_count": stats.get('edge_count', 0),
                "message": "知识图谱构建成功"
            }
            
        except Exception as e:
            logger.error(f"❌ 知识图谱构建失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "node_count": 0,
                "edge_count": 0
            }
    
    async def search_knowledge(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """搜索知识图谱"""
        if not self.is_available():
            return {
                "success": False,
                "error": "Graphiti 客户端不可用",
                "entities": [],
                "relationships": [],
                "total_count": 0
            }
        
        try:
            logger.info(f"🔍 搜索知识图谱: {query}")
            
            # 使用 Graphiti 的搜索功能
            search_results = await self.client.search(
                query=query,
                num_results=limit
            )
            
            logger.info(f"✅ 搜索完成，找到 {len(search_results)} 个结果")
            
            # 分离实体和关系（如果搜索结果包含这些信息）
            entities = []
            relationships = []
            
            for result in search_results:
                # 根据结果类型分类
                if hasattr(result, 'uuid') and hasattr(result, 'name'):
                    # 这是一个实体
                    entities.append({
                        "uuid": getattr(result, 'uuid', ''),
                        "name": getattr(result, 'name', ''),
                        "summary": getattr(result, 'summary', ''),
                        "type": getattr(result, 'type', 'entity')
                    })
                else:
                    # 其他类型的结果
                    entities.append({
                        "uuid": str(id(result)),
                        "name": str(result)[:100] if len(str(result)) > 100 else str(result),
                        "summary": str(result),
                        "type": "search_result"
                    })
            
            return {
                "success": True,
                "entities": entities,
                "relationships": relationships,
                "total_count": len(search_results)
            }
            
        except Exception as e:
            logger.error(f"❌ 知识图谱搜索失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "entities": [],
                "relationships": [],
                "total_count": 0
            }
    
    async def get_graph_stats(self) -> Dict[str, Any]:
        """获取知识图谱统计信息"""
        if not self.is_available():
            return {
                "node_count": 0,
                "edge_count": 0,
                "episode_count": 0,
                "status": "不可用"
            }
        
        try:
            # 从Neo4j数据库中获取真实的统计信息
            from neo4j import GraphDatabase
            
            # 使用相同的连接配置
            driver = GraphDatabase.driver(
                "bolt://localhost:7687",
                auth=("neo4j", "bridge123")
            )
            
            with driver.session() as session:
                # 获取节点数量
                node_result = session.run("MATCH (n) RETURN count(n) as node_count")
                node_count = node_result.single()["node_count"]
                
                # 获取关系数量
                edge_result = session.run("MATCH ()-[r]->() RETURN count(r) as edge_count")
                edge_count = edge_result.single()["edge_count"]
                
                # 获取Episode节点数量
                episode_result = session.run("MATCH (n:Episodic) RETURN count(n) as episode_count")
                episode_count = episode_result.single()["episode_count"]
            
            driver.close()
            
            logger.info(f"📊 获取到真实统计数据: 节点={node_count}, 关系={edge_count}, Episodes={episode_count}")
            
            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "episode_count": episode_count,
                "status": "正常"
            }
            
        except Exception as e:
            logger.error(f"❌ 获取图谱统计失败: {e}")
            return {
                "node_count": 0,
                "edge_count": 0,
                "episode_count": 0,
                "status": f"错误: {e}"
            }
    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            "status": "healthy" if self.is_available() else "unhealthy",
            "client_available": self.is_available(),
            "neo4j_connected": self.is_available(),  # 简化检查
            "message": "Graphiti 服务正常" if self.is_available() else "Graphiti 服务不可用"
        }

# 全局实例
graphiti_service = GraphitiService()

async def build_knowledge_graph_from_pdf(
    pdf_content: PDFContent,
    document_name: str,
    group_id: Optional[str] = None
) -> KnowledgeGraphResult:
    """
    从 PDF 内容构建知识图谱
    
    Args:
        pdf_content: PDF 解析内容
        document_name: 文档名称
        group_id: 分组ID，默认使用配置中的桥梁工程分组
        
    Returns:
        KnowledgeGraphResult: 构建结果
    """
    if not graphiti_service.is_available():
        return KnowledgeGraphResult(
            success=False,
            entity_count=0,
            relationship_count=0,
            processing_time=0.0,
            group_id="",
            error_message="Graphiti 客户端不可用"
        )
    
    start_time = datetime.now()
    # 直接使用默认值，避免Settings冲突
    target_group_id = group_id or "bridge_engineering"
    
    try:
        logger.info(f"🚀 开始构建知识图谱 - 文档: {document_name}")
        logger.info(f"📊 文本长度: {len(pdf_content.text)} 字符")
        
        # 分段处理长文本，避免超过API限制
        text_chunks = _split_text(pdf_content.text, max_chunk_size=3000)
        total_entities = 0
        total_relationships = 0
        
        for i, chunk in enumerate(text_chunks):
            logger.info(f"📝 处理文本块 {i+1}/{len(text_chunks)}")
            
            # 添加重试机制
            max_retries = 3
            retry_delay = 5  # 秒
            
            for attempt in range(max_retries):
                try:
                    # 构建知识图谱
                    episode_result = await graphiti_service.build_knowledge_graph(
                        chunk,
                        f"{document_name}_chunk_{i+1}"
                    )
                    
                    logger.info(f"✅ 文本块 {i+1} 处理成功")
                    break
                    
                except Exception as e:
                    error_msg = str(e)
                    if "Rate limit exceeded" in error_msg:
                        if attempt < max_retries - 1:
                            logger.warning(f"⏳ 遇到速率限制，等待 {retry_delay} 秒后重试 (尝试 {attempt+1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            continue
                        else:
                            logger.error(f"❌ 达到最大重试次数，跳过文本块 {i+1}")
                    else:
                        logger.error(f"❌ 文本块 {i+1} 处理失败: {error_msg}")
                        break
        
        # 获取统计信息
        try:
            stats = await graphiti_service.get_graph_stats()
            total_entities = stats.get("node_count", 0)
            total_relationships = stats.get("edge_count", 0)
        except Exception as e:
            logger.warning(f"获取统计信息失败: {e}")
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"🎉 知识图谱构建完成")
        logger.info(f"📊 实体数量: {total_entities}, 关系数量: {total_relationships}")
        logger.info(f"⏱️ 处理时间: {processing_time:.2f} 秒")
        
        return KnowledgeGraphResult(
            success=True,
            entity_count=total_entities,
            relationship_count=total_relationships,
            processing_time=processing_time,
            group_id=target_group_id,
            error_message=None
        )
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        error_message = f"知识图谱构建失败: {str(e)}"
        logger.error(f"❌ {error_message}")
        
        return KnowledgeGraphResult(
            success=False,
            entity_count=0,
            relationship_count=0,
            processing_time=processing_time,
            group_id=target_group_id,
            error_message=error_message
        )

def _prepare_episode_content(pdf_content: PDFContent, document_name: str) -> str:
    """
    准备用于 Graphiti 的内容
    
    Args:
        pdf_content: PDF 内容
        document_name: 文档名称
        
    Returns:
        str: 格式化的内容
    """
    content_parts = []
    
    # 添加文档基本信息
    content_parts.append(f"文档名称: {document_name}")
    content_parts.append(f"页数: {pdf_content.page_count}")
    content_parts.append(f"文档类型: 桥梁工程技术文档")
    
    # 添加元数据信息
    if pdf_content.metadata.get("title"):
        content_parts.append(f"文档标题: {pdf_content.metadata['title']}")
    if pdf_content.metadata.get("author"):
        content_parts.append(f"作者: {pdf_content.metadata['author']}")
    if pdf_content.metadata.get("subject"):
        content_parts.append(f"主题: {pdf_content.metadata['subject']}")
    
    # 添加主要文本内容 - 这是最重要的部分
    content_parts.append("\n=== 桥梁工程技术内容 ===")
    
    # 清理并优化文本内容用于知识图谱提取
    clean_text = _clean_text_for_kg(pdf_content.text)
    content_parts.append(clean_text)
    
    # 添加 OCR 识别的图像文本
    ocr_texts = []
    for image in pdf_content.images:
        if image.get("ocr_text"):
            ocr_texts.append(f"图像 {image['name']}: {image['ocr_text']}")
    
    if ocr_texts:
        content_parts.append("\n=== 图像识别的技术内容 ===")
        content_parts.extend(ocr_texts)
    
    # 添加表格信息
    if pdf_content.tables:
        content_parts.append("\n=== 表格数据 ===")
        for i, table in enumerate(pdf_content.tables):
            content_parts.append(f"表格 {i+1}: {table.get('summary', '技术数据表')}")
    
    final_content = "\n".join(content_parts)
    
    # 限制内容长度，避免太长的文本影响LLM处理
    if len(final_content) > 50000:  # 50K字符限制
        logger.warning(f"文档内容过长({len(final_content)}字符)，将截断到50K字符")
        final_content = final_content[:50000] + "\n...[内容已截断]"
    
    return final_content

def _clean_text_for_kg(text: str) -> str:
    """
    清理文本用于知识图谱提取
    """
    import re
    
    # 移除过多的空行
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    
    # 移除页眉页脚标记
    text = re.sub(r'--- 第 \d+ 页 ---', '', text)
    
    # 移除过多的空格
    text = re.sub(r' +', ' ', text)
    
    # 保留有意义的换行，但移除孤立的短行
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if len(line) > 3:  # 保留长度大于3的行
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def _split_text(text: str, max_chunk_size: int = 3000) -> List[str]:
    """
    将长文本分割成较小的块
    
    Args:
        text: 需要分割的文本
        max_chunk_size: 每块的最大字符数
        
    Returns:
        List[str]: 分割后的文本块列表
    """
    if len(text) <= max_chunk_size:
        return [text]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(text):
        # 计算当前块的结束位置
        end_pos = min(current_pos + max_chunk_size, len(text))
        
        # 如果不是最后一块，尝试在句号或换行符处分割
        if end_pos < len(text):
            # 向前查找最近的句号或换行符
            for i in range(end_pos, current_pos, -1):
                if text[i] in '.。\n':
                    end_pos = i + 1
                    break
        
        chunk = text[current_pos:end_pos].strip()
        if chunk:
            chunks.append(chunk)
        
        current_pos = end_pos
    
    return chunks

async def search_entities(
    query: str, 
    group_id: Optional[str] = None,
    limit: int = 50
) -> SearchResult:
    """
    搜索实体
    
    Args:
        query: 搜索查询
        group_id: 分组ID
        limit: 结果限制数量
        
    Returns:
        SearchResult: 搜索结果
    """
    if not graphiti_service.is_available():
        return SearchResult(entities=[], relationships=[], total_count=0)
    
    try:
        actual_group_id = group_id or get_settings().GRAPHITI_GROUP_ID
        
        # 使用 Graphiti 搜索
        search_results = await graphiti_service.search_knowledge(
            query=query,
            limit=limit
        )
        
        entities = search_results.get("entities", [])
        
        return SearchResult(
            entities=entities,
            relationships=search_results.get("relationships", []),
            total_count=search_results.get("total_count", 0)
        )
        
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return SearchResult(entities=[], relationships=[], total_count=0)

async def get_entity_relationships(
    entity_uuid: str, 
    group_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    获取实体的关系
    
    Args:
        entity_uuid: 实体 UUID
        group_id: 分组ID
        
    Returns:
        List[Dict[str, Any]]: 关系列表
    """
    # TODO: 实现实体关系查询
    # 需要直接查询 Neo4j 数据库
    return []

async def export_knowledge_corpus(
    group_id: Optional[str] = None,
    format_type: str = "jsonl"
) -> str:
    """
    导出知识图谱作为训练语料
    
    Args:
        group_id: 分组ID
        format_type: 导出格式 (jsonl, txt, csv)
        
    Returns:
        str: 导出文件路径
    """
    actual_group_id = group_id or get_settings().GRAPHITI_GROUP_ID
    
    try:
        # 获取所有实体和关系
        search_result = await search_entities(query="", group_id=actual_group_id, limit=10000)
        
        # 根据格式导出
        if format_type == "jsonl":
            return await _export_jsonl(search_result, actual_group_id)
        elif format_type == "txt":
            return await _export_txt(search_result, actual_group_id)
        elif format_type == "csv":
            return await _export_csv(search_result, actual_group_id)
        else:
            raise ValueError(f"不支持的导出格式: {format_type}")
            
    except Exception as e:
        logger.error(f"导出知识语料失败: {str(e)}")
        raise

async def _export_jsonl(search_result: SearchResult, group_id: str) -> str:
    """导出为 JSONL 格式"""
    import json
    
    output_file = f"exports/knowledge_corpus_{group_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    # 确保导出目录存在
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for entity in search_result.entities:
            # 转换为训练格式
            corpus_item = {
                "text": entity.get("summary", ""),
                "entity": entity.get("name", ""),
                "domain": "bridge_engineering",
                "source": "knowledge_graph"
            }
            f.write(json.dumps(corpus_item, ensure_ascii=False) + '\n')
    
    return output_file

async def _export_txt(search_result: SearchResult, group_id: str) -> str:
    """导出为文本格式"""
    output_file = f"exports/knowledge_corpus_{group_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for entity in search_result.entities:
            f.write(f"实体: {entity.get('name', '')}\n")
            f.write(f"描述: {entity.get('summary', '')}\n")
            f.write("=" * 50 + "\n")
    
    return output_file

async def _export_csv(search_result: SearchResult, group_id: str) -> str:
    """导出为 CSV 格式"""
    import csv
    
    output_file = f"exports/knowledge_corpus_{group_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['entity_name', 'summary', 'domain', 'source'])
        
        for entity in search_result.entities:
            writer.writerow([
                entity.get('name', ''),
                entity.get('summary', ''),
                'bridge_engineering',
                'knowledge_graph'
            ])
    
    return output_file

# 全局服务实例
graphiti_service: Optional[GraphitiService] = None

def get_graphiti_service() -> GraphitiService:
    """获取 Graphiti 服务实例"""
    global graphiti_service
    
    if graphiti_service is None:
        logger.info("🔧 初始化 Graphiti 服务...")
        try:
            graphiti_service = GraphitiService()
            logger.info("✅ Graphiti 服务初始化成功")
        except Exception as e:
            logger.error(f"❌ Graphiti 服务初始化失败: {e}")
            # 创建一个不可用的服务实例
            graphiti_service = GraphitiService.__new__(GraphitiService)
            graphiti_service.client = None
    
    return graphiti_service

def reset_graphiti_service():
    """重置 Graphiti 服务（用于测试）"""
    global graphiti_service
    graphiti_service = None 