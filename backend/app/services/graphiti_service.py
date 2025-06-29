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
                # Corrected import path
                from ..services.deepseek_client import DeepSeekClient
                from ..services.deepseek_embedder import DeepSeekEmbedder
                
                # 配置 DeepSeek LLM（使用自定义客户端）
                settings = get_settings()
                llm_config = LLMConfig(
                    api_key=settings.OPENAI_API_KEY if settings.OPENAI_API_KEY else "sk-0b26cde0319b451e984c38a0734353e7", # Use env var if available
                    model="deepseek-chat", # This could also be from settings
                    base_url="https://api.deepseek.com/v1" # This could also be from settings
                )
                llm_client = DeepSeekClient(config=llm_config)
                
                # 使用自定义嵌入器，避免调用OpenAI API
                embedder = DeepSeekEmbedder()
                
                # 配置Graphiti，使用DeepSeek LLM和自定义嵌入器
                self.client = Graphiti(
                    uri=settings.NEO4J_URI,
                    user=settings.NEO4J_USER,
                    password=settings.NEO4J_PASSWORD,
                    llm_client=llm_client,
                    embedder=embedder
                    # cross_encoder=None (默认，避免额外API调用)
                )
                logger.info("✅ Graphiti 客户端初始化成功（使用DeepSeek API）")
                return
            except ImportError as ie:
                logger.error(f"⚠️ DeepSeek组件导入失败: {ie}")
            except Exception as e1:
                logger.warning(f"⚠️ DeepSeek初始化失败: {e1}")
            
            # 方式2：使用环境变量中的OpenAI配置（备用）
            settings = get_settings() # Ensure settings are loaded
            if settings.OPENAI_API_KEY: # Check settings instead of raw os.environ
                try:
                    self.client = Graphiti(
                        uri=settings.NEO4J_URI,
                        user=settings.NEO4J_USER,
                        password=settings.NEO4J_PASSWORD
                        # This will use OpenAI by default if OPENAI_API_KEY is set in env
                    )
                    logger.info("✅ Graphiti 客户端初始化成功（使用OpenAI配置）")
                    return
                except Exception as e2:
                    logger.warning(f"⚠️ OpenAI初始化失败: {e2}")
            
            # 方式3：最简单的初始化（最后备用, no LLM or custom embedder）
            try:
                settings = get_settings() # Ensure settings are loaded
                self.client = Graphiti(
                    uri=settings.NEO4J_URI,
                    user=settings.NEO4J_USER,
                    password=settings.NEO4J_PASSWORD,
                    llm_client=None, # Explicitly no LLM if other setups failed
                    embedder=None    # Explicitly no embedder
                )
                logger.info("✅ Graphiti 客户端初始化成功（使用默认配置, 无 LLM/Embedder）")
                return
            except Exception as e3:
                logger.warning(f"⚠️ 默认初始化失败: {e3}")
            
            logger.error("❌ 所有Graphiti初始化方式都失败了。Graphiti服务将不可用。")
            self.client = None # Ensure client is None if all attempts fail
            
        except Exception as e: # Catch-all for any unexpected error during the process
            logger.error(f"❌ Graphiti 客户端初始化过程中发生严重错误: {e}")
            self.client = None


    def is_available(self) -> bool:
        """检查 Graphiti 是否可用"""
        return self.client is not None
    
    async def build_knowledge_graph(self, text: str, document_id: str) -> Dict[str, Any]:
        """构建知识图谱"""
        if not self.is_available() or not self.client: # Added self.client check for clarity
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
            
            # Step 1: Extract entities and relationships using LLM
            extracted_data = await self._extract_entities_and_relationships_with_llm(text)
            llm_summary = extracted_data.get("summary")
            entities = extracted_data.get("entities", [])
            relationships = extracted_data.get("relationships", [])

            logger.info(f"🧠 LLM Extracted: {len(entities)} entities, {len(relationships)} relationships.")
            if llm_summary:
                logger.info(f"📝 LLM Summary: {llm_summary[:100]}...") # Log first 100 chars

            # Step 2: Add the main text as an Episode node
            # We might pass the llm_summary to add_episode if it accepts a summary argument,
            # or store it as a property. For now, Graphiti's default summary behavior for episode_body is used.
            # If Graphiti's add_episode also does its own extraction, we need to be mindful of duplication
            # or find a way to tell it to only store the episode.
            # For now, let's assume add_episode is primarily for creating the Episodic node.
            episode_node = await self.client.add_episode(
                name=episode_name,
                episode_body=text, # Original text for context
                summary=llm_summary, # Pass the LLM generated summary
                source_description="桥梁工程技术文档 (Processed Chunk)",
                reference_time=datetime.now(),
                source=EpisodeType.text
            )
            logger.info(f"✅ Episodic node '{episode_name}' added/updated: {episode_node}")

            # Step 3: Add extracted entities and relationships to the graph
            # This part will be significantly enhanced in the "Enhance Graph Construction Logic" step.
            # For now, we're just logging that we would do it.
            # We'll need to ensure entities are not duplicated if they already exist.
            
            actual_created_entities = 0
            actual_created_relationships = 0
            
            # This map will store llm_entity_id -> graph_node_uuid
            llm_to_graph_entity_id_map = {}

            if entities:
                try:
                    actual_created_entities, llm_to_graph_entity_id_map = await self._store_graph_entities(
                        entities,
                        episode_node_id=episode_node.uuid if episode_node else None
                    )
                    logger.info(f"📝 Successfully stored/merged {actual_created_entities} entities for episode {episode_name}.")
                except Exception as entity_ex:
                    logger.error(f"Error storing entities for {episode_name}: {entity_ex}", exc_info=True)
            
            if relationships and llm_to_graph_entity_id_map:
                try:
                    actual_created_relationships = await self._store_graph_relationships(
                        relationships,
                        llm_to_graph_entity_id_map,
                        episode_node_id=episode_node.uuid if episode_node else None
                    )
                    logger.info(f"🔗 Successfully created {actual_created_relationships} relationships for episode {episode_name}.")
                except Exception as rel_ex:
                    logger.error(f"Error storing relationships for {episode_name}: {rel_ex}", exc_info=True)
            
            stats = await self.get_graph_stats()

            return {
                "success": True,
                "episode_name": episode_name,
                "llm_extracted_entities": len(entities),
                "llm_extracted_relationships": len(relationships),
                "actual_created_entities": actual_created_entities,
                "actual_created_relationships": actual_created_relationships,
                "total_graph_nodes": stats.get('node_count', 0),
                "total_graph_edges": stats.get('edge_count', 0),
                "message": "知识图谱构建流程完成."
            }
            
        except Exception as e:
            logger.error(f"❌ 知识图谱构建流程失败 for document chunk {document_id}: {e}", exc_info=True)
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
            if not self.client or not hasattr(self.client, 'graph_db') or not self.client.graph_db:
                logger.error("❌ Neo4j driver (self.client.graph_db) is not available for get_graph_stats.")
                return {
                    "node_count": 0, "edge_count": 0, "episode_count": 0,
                    "status": "错误: Neo4j driver not initialized in Graphiti client"
                }

            async with self.client.graph_db.session() as session:
                # 获取节点数量
                node_result = await session.run("MATCH (n) RETURN count(n) as node_count")
                node_record = await node_result.single()
                node_count = node_record["node_count"] if node_record else 0
                
                # 获取关系数量
                edge_result = await session.run("MATCH ()-[r]->() RETURN count(r) as edge_count")
                edge_record = await edge_result.single()
                edge_count = edge_record["edge_count"] if edge_record else 0
                
                # 获取Episode节点数量 (ensure label is correct, Graphiti uses Episodic)
                episode_result = await session.run("MATCH (n:Episodic) RETURN count(n) as episode_count")
                episode_record = await episode_result.single()
                episode_count = episode_record["episode_count"] if episode_record else 0
            
            logger.info(f"📊 Graph stats via self.client.graph_db: Nodes={node_count}, Edges={edge_count}, Episodes={episode_count}")
            
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

    async def get_health_status(self) -> Dict[str, Any]:
        """获取Graphiti服务和Neo4j连接的详细健康状态"""
        client_available = self.is_available()
        neo4j_actually_connected = False
        neo4j_error_message = None

        if client_available and self.client and self.client.graph_db:
            try:
                async with self.client.graph_db.session() as session:
                    result = await session.run("RETURN 1")
                    await result.single() # Consume the result
                neo4j_actually_connected = True
                logger.debug("Neo4j connection health check successful.")
            except Exception as e:
                neo4j_error_message = str(e)
                logger.error(f"Neo4j connection health check failed: {neo4j_error_message}", exc_info=True)
        elif not client_available:
            neo4j_error_message = "Graphiti client not available."
        else: # client available but graph_db somehow not
            neo4j_error_message = "Graphiti client available, but Neo4j driver (graph_db) is not."


        overall_status = "healthy" if client_available and neo4j_actually_connected else "unhealthy"

        message = f"Graphiti Service: {'Available' if client_available else 'Unavailable'}. "
        message += f"Neo4j Connection: {'Connected' if neo4j_actually_connected else 'Disconnected'}"
        if neo4j_error_message and not neo4j_actually_connected:
            message += f" (Error: {neo4j_error_message})"

        return {
            "overall_status": overall_status,
            "graphiti_client_available": client_available,
            "neo4j_connection_status": "connected" if neo4j_actually_connected else "disconnected",
            "neo4j_error": neo4j_error_message if not neo4j_actually_connected else None,
            "message": message
        }

    async def _extract_entities_and_relationships_with_llm(self, text: str) -> Dict[str, Any]:
        """
        Uses the configured LLM client to extract entities and relationships from text.
        """
        if not self.client or not self.client.llm_client:
            logger.error("LLM client not available for extraction.")
            return {"summary": None, "entities": [], "relationships": []}

        # Define entity types and relationship types for bridge engineering
        entity_types = [
            "Material", "BridgeComponent", "ConstructionMethod", "DesignStandard",
            "Location", "Organization", "DamageType", "InspectionTechnique", "Permit",
            "Bridge", "BridgeSection", "Sensor", "MonitoringSystem", "Regulation", "Software",
            "EnvironmentalFactor", "LoadType", "GeotechnicalFeature"
        ]
        relationship_types = [
            "USES_MATERIAL", "HAS_COMPONENT", "EMPLOYS_METHOD", "COMPLIES_WITH_STANDARD",
            "LOCATED_AT", "PART_OF", "CONNECTS_TO", "MANUFACTURED_BY", "DESIGNED_BY", "HAS_SPECIFICATION",
            "CONSTRUCTED_BY", "HAS_DAMAGE", "DETECTS_DAMAGE", "APPLIES_TECHNIQUE", "REQUIRES_PERMIT",
            "SPECIFIED_IN", "MEASURES_PROPERTY", "MONITORS_COMPONENT", "ASSESSES_RISK", "ANALYZED_WITH",
            "AFFECTED_BY", "SUBJECT_TO_LOAD", "FOUNDED_ON"
        ]

        prompt = f"""\
You are an expert in knowledge graph extraction, specializing in Bridge Engineering.
From the provided text, please extract entities and their relationships.

**Instructions:**
1.  **Identify Entities:** Extract all relevant entities from the text. For each entity, provide:
    *   `id`: A unique temporary ID for the entity within this extraction (e.g., "e1", "e2"). Ensure this ID is unique within the list of entities you generate.
    *   `name`: The canonical name of the entity. Normalize variations (e.g., "steel grade S355", "S355 steel" -> "S355 Steel").
    *   `type`: The type of the entity. Choose from the following allowed types: {', '.join(entity_types)}. If an entity could fit multiple types, choose the most specific one.
    *   `properties` (optional): A dictionary of key-value pairs for any additional relevant attributes of the entity found in the text (e.g., {{ "strength_grade": "C50", "aggregate_size": "20mm" }} for a Material like concrete). Values should be strings or numbers.

2.  **Identify Relationships:** Extract relationships **only between the entities you identified above**. For each relationship, provide:
    *   `source_id`: The temporary ID of the source entity (must match an ID from your entities list).
    *   `target_id`: The temporary ID of the target entity (must match an ID from your entities list).
    *   `type`: The type of the relationship. Choose from the following allowed types: {', '.join(relationship_types)}.
    *   `properties` (optional): A dictionary of key-value pairs for any additional relevant attributes of the relationship (e.g., {{ "location_on_bridge": "deck" }}). Values should be strings or numbers.
    *   Avoid creating redundant or overly generic relationships. Focus on meaningful connections.

3.  **Generate Summary:** Provide a concise technical summary of the input text (around 2-3 sentences), focusing on the key information relevant to bridge engineering.

4.  **Output Format:** Return the output as a single, valid JSON object with three main keys: "summary" (string), "entities" (list of objects), and "relationships" (list of objects). Ensure the JSON is well-formed.

**Example Output Format:**
```json
{{
  "summary": "The text details the use of S355 steel for the main girders of the New River Bridge, which complies with Eurocode 3 design standards. Ultrasonic testing was employed for weld inspection.",
  "entities": [
    {{
      "id": "e1",
      "name": "New River Bridge",
      "type": "Bridge",
      "properties": {{ "location_city": "Exampleville" }}
    }},
    {{
      "id": "e2",
      "name": "S355 Steel",
      "type": "Material",
      "properties": {{ "yield_strength": "355 MPa" }}
    }},
    {{
      "id": "e3",
      "name": "Main Girders",
      "type": "BridgeComponent"
    }},
    {{
      "id": "e4",
      "name": "Eurocode 3",
      "type": "DesignStandard"
    }},
    {{
      "id": "e5",
      "name": "Ultrasonic Testing",
      "type": "InspectionTechnique"
    }},
    {{
      "id": "e6",
      "name": "Welds",
      "type": "BridgeComponent"
    }}
  ],
  "relationships": [
    {{
      "source_id": "e3",
      "target_id": "e2",
      "type": "USES_MATERIAL"
    }},
    {{
      "source_id": "e1",
      "target_id": "e3",
      "type": "HAS_COMPONENT"
    }},
    {{
      "source_id": "e1",
      "target_id": "e4",
      "type": "COMPLIES_WITH_STANDARD"
    }},
    {{
      "source_id": "e5",
      "target_id": "e6",
      "type": "DETECTS_DAMAGE",
      "properties": {{ "target_defect": "weld imperfections" }}
    }},
    {{
      "source_id": "e3",
      "target_id": "e6",
      "type": "HAS_COMPONENT"
    }}
  ]
}}
```

**Input Text:**
---
{text}
---

**JSON Output (ensure this is a single, valid JSON object):**
"""
        try:
            llm_client_internal = self.client.llm_client
            if not llm_client_internal: # Should have been caught by the check at the start of the method
                raise ValueError("LLM client is not initialized.")

            # Check for specific client methods for JSON output
            # This assumes DeepSeekClient might have specific ways to ask for JSON
            llm_response_content = None
            if hasattr(llm_client_internal, 'generate_text_v2') and callable(getattr(llm_client_internal, 'generate_text_v2')):
                # The `is_json_response` parameter is specific to graphiti-core's LLMClient interface
                # It might internally set headers or format the request for JSON output
                logger.debug("Using llm_client.generate_text_v2 for extraction.")
                llm_response_content = await llm_client_internal.generate_text_v2(
                    prompt=prompt,
                    is_json_response=True
                )
            elif hasattr(llm_client_internal, 'generate_text') and callable(getattr(llm_client_internal, 'generate_text')):
                logger.debug("Using llm_client.generate_text for extraction.")
                llm_response_content = await llm_client_internal.generate_text(prompt=prompt)
            # Example if using something like OpenAI's client directly (DeepSeekClient might wrap this)
            # elif hasattr(llm_client_internal, 'chat') and hasattr(llm_client_internal.chat, 'completions'):
            # logger.debug("Using llm_client.chat.completions.create for extraction.")
            # response = await llm_client_internal.chat.completions.create(
            # model=llm_client_internal.config.model, # Ensure model is available
            # messages=[{"role": "user", "content": prompt}],
            # response_format={"type": "json_object"} # This is specific to OpenAI API
            # )
            # llm_response_content = response.choices[0].message.content
            else:
                logger.error("DeepSeekClient does not have a recognized text generation method ('generate_text_v2' or 'generate_text').")
                return {"summary": None, "entities": [], "relationships": []}

            if not llm_response_content:
                logger.warning("LLM returned empty content.")
                return {"summary": None, "entities": [], "relationships": []}

            # Clean the response: remove markdown code block fences if present
            # Also handle potential leading/trailing whitespace or non-JSON text before/after the object
            match = re.search(r"\{.*\}", llm_response_content, re.DOTALL)
            if not match:
                logger.error(f"No JSON object found in LLM response. Response: {llm_response_content[:500]}")
                return {"summary": None, "entities": [], "relationships": []}

            cleaned_response = match.group(0)

            import json
            try:
                parsed_json = json.loads(cleaned_response)

                # Validate structure
                if not isinstance(parsed_json, dict) or \
                   not isinstance(parsed_json.get("summary"), str) or \
                   not isinstance(parsed_json.get("entities"), list) or \
                   not isinstance(parsed_json.get("relationships"), list):
                    logger.error(f"LLM output JSON structure is incorrect. Missing or wrong type for summary, entities, or relationships. Got: {cleaned_response[:500]}")
                    # Try to salvage parts if possible
                    return {
                        "summary": parsed_json.get("summary") if isinstance(parsed_json.get("summary"), str) else "Summary extraction failed.",
                        "entities": parsed_json.get("entities") if isinstance(parsed_json.get("entities"), list) else [],
                        "relationships": parsed_json.get("relationships") if isinstance(parsed_json.get("relationships"), list) else []
                    }

                validated_summary = parsed_json.get("summary", "Summary not provided.")
                validated_entities = self._validate_llm_entities(parsed_json.get("entities", []), entity_types)
                validated_relationships = self._validate_llm_relationships(parsed_json.get("relationships", []), relationship_types, {e['id'] for e in validated_entities})

                logger.info(f"LLM JSON response parsed. Validated entities: {len(validated_entities)}, Validated relationships: {len(validated_relationships)}. Summary: {validated_summary[:100]}...")
                return {
                    "summary": validated_summary,
                    "entities": validated_entities,
                    "relationships": validated_relationships
                }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from LLM: {e}. Response snippet: {cleaned_response[:500]}")
                return {"summary": None, "entities": [], "relationships": []}

        except Exception as e:
            logger.error(f"Error during LLM extraction: {e}", exc_info=True)
            return {"summary": None, "entities": [], "relationships": []}

    def _validate_llm_entities(self, entities_data: List[Dict[str, Any]], allowed_types: List[str]) -> List[Dict[str, Any]]:
        validated_entities = []
        seen_entity_ids = set()
        for entity in entities_data:
            if not isinstance(entity, dict):
                logger.warning(f"Skipping non-dict entity item: {entity}")
                continue

            entity_id = entity.get("id")
            name = entity.get("name")
            entity_type = entity.get("type")

            if not all([entity_id, name, entity_type]):
                logger.warning(f"Entity missing required fields (id, name, type): {entity}")
                continue
            if not isinstance(entity_id, str) or not isinstance(name, str) or not isinstance(entity_type, str):
                logger.warning(f"Entity fields (id, name, type) are not strings: {entity}")
                continue
            if entity_id in seen_entity_ids:
                logger.warning(f"Duplicate entity ID '{entity_id}' found in LLM output. Skipping.")
                continue

            if entity_type not in allowed_types:
                logger.warning(f"Unsupported entity type '{entity_type}' for entity '{name}'. Defaulting to 'GenericEntity' or consider skipping.")
                # Option 1: Skip
                # continue
                # Option 2: Default type (ensure 'GenericEntity' is handled or added to sanitize_label logic if used)
                # entity['type'] = 'GenericEntity'
                # For now, we allow it but it might cause issues with sanitize_label if not in predefined list for specific label creation
                # The sanitize_label function itself is robust enough. The main check is for prompt consistency.
                # Let's assume for now the prompt is good and types are from the list. If not, `sanitize_label` will handle it.
                # No, it's better to enforce: if type not in allowed_types, log and skip.
                logger.warning(f"Entity type '{entity_type}' not in allowed list. Skipping entity: {name}")
                continue


            seen_entity_ids.add(entity_id)
            validated_entities.append(entity)
        return validated_entities

    def _validate_llm_relationships(self, relationships_data: List[Dict[str, Any]], allowed_types: List[str], valid_entity_ids: set) -> List[Dict[str, Any]]:
        validated_relationships = []
        for rel in relationships_data:
            if not isinstance(rel, dict):
                logger.warning(f"Skipping non-dict relationship item: {rel}")
                continue

            source_id = rel.get("source_id")
            target_id = rel.get("target_id")
            rel_type = rel.get("type")

            if not all([source_id, target_id, rel_type]):
                logger.warning(f"Relationship missing required fields (source_id, target_id, type): {rel}")
                continue
            if not isinstance(source_id, str) or not isinstance(target_id, str) or not isinstance(rel_type, str):
                logger.warning(f"Relationship fields (source_id, target_id, type) are not strings: {rel}")
                continue

            if rel_type not in allowed_types:
                logger.warning(f"Unsupported relationship type '{rel_type}'. Skipping relationship: {source_id}->{target_id}")
                continue

            if source_id not in valid_entity_ids:
                logger.warning(f"Source entity ID '{source_id}' for relationship '{rel_type}' not found in valid entities. Skipping.")
                continue
            if target_id not in valid_entity_ids:
                logger.warning(f"Target entity ID '{target_id}' for relationship '{rel_type}' not found in valid entities. Skipping.")
                continue
            if source_id == target_id:
                logger.warning(f"Self-referential relationship for entity ID '{source_id}' of type '{rel_type}'. Skipping.")
                continue

            validated_relationships.append(rel)
        return validated_relationships

    async def _store_graph_entities(self, extracted_entities: List[Dict[str, Any]], episode_node_id: Optional[str]) -> (int, Dict[str, str]):
        """
        Stores extracted entities in Neo4j using Graphiti.
        Merges based on name and type. Links to the episode.
        Returns the count of new entities created and a map of llm_id to graph_uuid.
        """
        if not self.client:
            logger.error("Graphiti client not available for storing entities.")
            return 0, {}

        created_count = 0
        llm_to_graph_id_map = {} # Maps temporary LLM ID to actual graph node UUID

        for entity_data in extracted_entities:
            llm_entity_id = entity_data.get("id")
            entity_name = entity_data.get("name")
            entity_type = entity_data.get("type")
            properties = entity_data.get("properties", {})

            if not entity_name or not entity_type or not llm_entity_id:
                logger.warning(f"Skipping entity due to missing id, name, or type: {entity_data}")
                continue

            # Prepare properties for Neo4j. Ensure all values are Neo4j-compatible.
            # Graphiti's add_node/add_entity_to_episode should handle this, but good to be aware.
            node_props = {
                "name": entity_name,
                "entity_type": entity_type, # Store original type if Graphiti uses a generic 'Entity' label
                "last_seen": datetime.now().isoformat(),
                **properties # Add LLM-extracted properties
            }

            # Labels for the node: a generic "Entity" label and a specific type label
            labels = ["Entity", entity_type.replace(" ", "_")] # Ensure type label is valid

            try:
                # Graphiti's `add_node` can be used for MERGE-like behavior if a unique property is specified.
                # Let's assume we want to merge on name and type.
                # If Graphiti's `add_node` doesn't support MERGE directly on a combination of properties
                # or creating relationships like MENTIONED_IN simultaneously,
                # we might need to run custom Cypher.
                # For now, let's try a simple add_node and then link.
                # Graphiti's `add_entity_to_episode` might be more appropriate.
                # It usually creates an Entity node (if not exists) and links it to the episode.

                # Option 1: Using add_entity_to_episode (Preferred if it handles MERGE logic)
                # This method might require the entity type to be passed differently or might use its own logic.
                # We need to know if it merges based on name or if it always creates.
                # Let's assume it tries to find an entity by name and type, or creates a new one.

                # graph_entity = await self.client.add_entity_to_episode(
                # episode_id=episode_node_id, # UUID of the EpisodicNode
                # entity_name=entity_name,
                # entity_type=entity_type, # This might be a specific param or part of props
                # entity_properties=node_props,
                # create_if_not_exists=True # Assuming this option exists
                # )
                # if graph_entity and hasattr(graph_entity, 'uuid'):
                #    llm_to_graph_id_map[llm_entity_id] = graph_entity.uuid
                #    # How to count "newly created"? add_entity_to_episode might not return this directly.
                # else:
                #    logger.warning(f"Could not add/retrieve entity {entity_name} via add_entity_to_episode.")
                #    continue

                # Option 2: Custom Cypher for precise MERGE and property updates (More control)
                # This provides more control over merging and setting properties.
                # `graph_db` is Graphiti's Neo4j driver instance
                cypher_query = f"""
                MERGE (e:Entity:{sanitize_label(entity_type)} {{name: $name, entity_type: $entity_type}})
                ON CREATE SET e.created_at = timestamp(), e.uuid = randomUUID(), e += $props, e.first_seen = timestamp()
                ON MATCH SET e += $props, e.last_seen = timestamp()
                RETURN e.uuid as uuid, e.created_at = e.first_seen as created
                """
                # `sanitize_label` is a helper to ensure entity_type is a valid Neo4j label

                params = {"name": entity_name, "entity_type": entity_type, "props": node_props}

                async with self.client.graph_db.session() as session:
                    result = await session.run(cypher_query, params)
                    record = await result.single()
                    if record and record["uuid"]:
                        graph_node_uuid = record["uuid"]
                        llm_to_graph_id_map[llm_entity_id] = graph_node_uuid
                        if record["created"]:
                            created_count += 1

                        # Link to episode if episode_node_id is provided
                        if episode_node_id:
                            await self._link_entity_to_episode(graph_node_uuid, episode_node_id)
                    else:
                        logger.warning(f"Failed to merge or retrieve entity: {entity_name} of type {entity_type}")
                        continue

            except Exception as ex:
                logger.error(f"Error storing entity {entity_name} ({entity_type}): {ex}", exc_info=True)
                continue

        logger.info(f"Finished storing entities. Total processed: {len(extracted_entities)}, New additions: {created_count}")
        return created_count, llm_to_graph_id_map

    async def _link_entity_to_episode(self, entity_uuid: str, episode_uuid: str):
        """Creates a MENTIONS relationship from an Episode to an Entity."""
        if not self.client:
            return
        try:
            # Graphiti might have a specific method for this. If not, use Cypher.
            # e.g., await self.client.link_entity_to_episode(entity_uuid, episode_uuid, "MENTIONS")
            cypher = """
            MATCH (ep:Episodic {uuid: $episode_uuid})
            MATCH (en:Entity {uuid: $entity_uuid})
            MERGE (ep)-[r:MENTIONS]->(en)
            ON CREATE SET r.timestamp = timestamp()
            RETURN type(r)
            """
            async with self.client.graph_db.session() as session:
                await session.run(cypher, episode_uuid=episode_uuid, entity_uuid=entity_uuid)
            logger.debug(f"Linked entity {entity_uuid} to episode {episode_uuid}")
        except Exception as e:
            logger.error(f"Failed to link entity {entity_uuid} to episode {episode_uuid}: {e}", exc_info=True)


    async def _store_graph_relationships(
        self,
        extracted_relationships: List[Dict[str, Any]],
        llm_to_graph_entity_id_map: Dict[str, str],
        episode_node_id: Optional[str] # For context, if relationships are also directly linked to episodes
    ) -> int:
        """
        Stores extracted relationships in Neo4j using Graphiti.
        """
        if not self.client:
            logger.error("Graphiti client not available for storing relationships.")
            return 0

        created_count = 0
        for rel_data in extracted_relationships:
            source_llm_id = rel_data.get("source_id")
            target_llm_id = rel_data.get("target_id")
            rel_type = rel_data.get("type")
            properties = rel_data.get("properties", {})

            if not source_llm_id or not target_llm_id or not rel_type:
                logger.warning(f"Skipping relationship due to missing source/target id or type: {rel_data}")
                continue

            source_graph_uuid = llm_to_graph_entity_id_map.get(source_llm_id)
            target_graph_uuid = llm_to_graph_entity_id_map.get(target_llm_id)

            if not source_graph_uuid or not target_graph_uuid:
                logger.warning(f"Skipping relationship {rel_type} due to missing source/target graph UUID for LLM IDs {source_llm_id}, {target_llm_id}.")
                continue

            # Ensure relationship type is valid for Cypher
            sanitized_rel_type = sanitize_label(rel_type, is_relationship_type=True)

            # Filter out problematic/unwanted properties before storing
            unwanted_rel_props = ["episodes", "expired_at", "invalid_at"]
            sanitized_rel_llm_props = {k: v for k, v in properties.items() if k not in unwanted_rel_props}
            if len(properties) != len(sanitized_rel_llm_props):
                logger.debug(f"Filtered out {len(properties) - len(sanitized_rel_llm_props)} unwanted properties from LLM-extracted relationship properties for type {rel_type}.")


            try:
                # Graphiti's add_edge might be:
                # await self.client.add_edge(source_node_uuid, target_node_uuid, rel_type, properties=sanitized_rel_llm_props)
                # Or using Cypher for more control (e.g., MERGE to avoid duplicate relationships if properties should be unique)
                cypher_query = f"""
                MATCH (source:Entity {{uuid: $source_uuid}})
                MATCH (target:Entity {{uuid: $target_uuid}})
                MERGE (source)-[r:`{sanitized_rel_type}`]->(target)
                ON CREATE SET r = $props, r.created_at = timestamp()
                ON MATCH SET r += $props, r.last_updated_at = timestamp()
                RETURN type(r) is not null as created_or_matched
                """
                # Note: MERGE on relationships typically matches on type and nodes.
                # If properties need to be part of the uniqueness, the MERGE query would be more complex.
                # For now, this merges if the same type of relationship exists between these two nodes, and updates properties.

                async with self.client.graph_db.session() as session:
                    result = await session.run(cypher_query,
                                               source_uuid=source_graph_uuid,
                                               target_uuid=target_graph_uuid,
                                               props=sanitized_rel_llm_props) # Use sanitized props
                    record = await result.single()
                    if record and record["created_or_matched"]: # Assuming MERGE always returns the rel if matched/created
                        created_count +=1 # This counts merged relationships as "created" for simplicity here.
                                         # A more precise count of *new* relationships would require checking if r.created_at was set in this transaction.

                # Optionally, link relationship to episode (less common than linking entities)
                # if episode_node_id and created_rel:
                #    await self._link_relationship_to_episode(created_rel.id, episode_node_id)

            except Exception as ex:
                logger.error(f"Error storing relationship {source_graph_uuid} -[{rel_type}]-> {target_graph_uuid}: {ex}", exc_info=True)

        logger.info(f"Finished storing relationships. Processed: {len(extracted_relationships)}, Created/Merged: {created_count}")
        return created_count

def sanitize_label(label_name: str, is_relationship_type: bool = False) -> str:
    """Sanitizes a string to be a valid Neo4j label or relationship type."""
    if not label_name:
        return "_MISSING_LABEL_" if not is_relationship_type else "_MISSING_REL_TYPE_"
    # Remove or replace invalid characters
    # Valid characters are typically alphanumeric and underscore. Cannot start with a number.
    # For relationship types, they are usually uppercased with underscores.
    # For labels, PascalCase is common.

    if is_relationship_type:
        label_name = label_name.upper()
        processed_label = re.sub(r'[^A-Z0-9_]', '_', label_name)
        if not re.match(r'^[A-Z_]', processed_label): # Must start with letter or underscore
            processed_label = "_" + processed_label
    else: # Node Label
        processed_label = re.sub(r'[^a-zA-Z0-9_]', '', label_name)
        if not re.match(r'^[a-zA-Z_]', processed_label):
             processed_label = "_" + processed_label

    if not processed_label: # Handle case where all chars were invalid
        return "_INVALID_LABEL_PROCESSED_" if not is_relationship_type else "_INVALID_REL_TYPE_PROCESSED_"
    return processed_label

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
        text_chunks = _split_text(pdf_content.text, max_chunk_size=3000) # Assuming max_chunk_size is in characters
        
        # Accumulators for entities and relationships created/processed for THIS document
        doc_specific_actual_entities_created = 0
        doc_specific_actual_relationships_created = 0
        doc_specific_llm_extracted_entities = 0
        doc_specific_llm_extracted_relationships = 0
        all_chunks_successful = True

        for i, chunk in enumerate(text_chunks):
            logger.info(f"📝 Processing text chunk {i+1}/{len(text_chunks)} for document '{document_name}'")
            
            max_retries = 3
            retry_delay = 5  # seconds
            episode_result = None # Define episode_result before the loop

            for attempt in range(max_retries):
                try:
                    cleaned_chunk = _clean_text_for_kg(chunk)
                    if not cleaned_chunk.strip():
                        logger.info(f"⏭️ Text chunk {i+1}/{len(text_chunks)} is empty after cleaning, skipping.")
                        episode_result = {"success": True, "actual_created_entities": 0, "actual_created_relationships": 0, "llm_extracted_entities": 0, "llm_extracted_relationships": 0}
                        break

                    logger.debug(f"Cleaned chunk {i+1} to be processed (first 100 chars): {cleaned_chunk[:100]}...")

                    episode_result = await graphiti_service.build_knowledge_graph(
                        cleaned_chunk,
                        f"{document_name}_chunk_{i+1}" # document_id for this chunk
                    )
                    
                    if episode_result.get("success"):
                        logger.info(f"✅ Text chunk {i+1}/{len(text_chunks)} processed successfully.")
                    else:
                        logger.error(f"❌ Text chunk {i+1}/{len(text_chunks)} processing reported failure: {episode_result.get('error', 'Unknown error')}")
                        all_chunks_successful = False # Mark that at least one chunk failed

                    break # Break from retry loop (either success or non-retryable failure from build_knowledge_graph)
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ Exception during processing chunk {i+1}/{len(text_chunks)}, attempt {attempt+1}/{max_retries}: {error_msg}", exc_info=True)
                    all_chunks_successful = False
                    episode_result = {"success": False, "error": error_msg, "actual_created_entities": 0, "actual_created_relationships": 0, "llm_extracted_entities": 0, "llm_extracted_relationships": 0}

                    if "Rate limit exceeded" in error_msg: # Or other identifiable retryable errors
                        if attempt < max_retries - 1:
                            logger.warning(f"⏳ Rate limit or retryable error. Waiting {retry_delay}s before retry {attempt+2}/{max_retries}.")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error(f"❌ Max retries reached for chunk {i+1}/{len(text_chunks)}. Skipping this chunk.")
                            break # Break from retry loop, chunk processing failed
                    else:
                        logger.error(f"❌ Non-retryable error for chunk {i+1}/{len(text_chunks)}. Skipping retries for this chunk.")
                        break # Break from retry loop, chunk processing failed

            # Aggregate results from this chunk if episode_result is not None
            if episode_result:
                doc_specific_actual_entities_created += episode_result.get("actual_created_entities", 0)
                doc_specific_actual_relationships_created += episode_result.get("actual_created_relationships", 0)
                doc_specific_llm_extracted_entities += episode_result.get("llm_extracted_entities", 0)
                doc_specific_llm_extracted_relationships += episode_result.get("llm_extracted_relationships", 0)

        processing_time = (datetime.now() - start_time).total_seconds()
        
        final_success_status = all_chunks_successful # Document processing is successful if all chunks are (or skipped cleanly)

        logger.info(f"🎉 Knowledge graph construction process for document '{document_name}' completed.")
        logger.info(f"📄 Document Summary: LLM Extracted Entities: {doc_specific_llm_extracted_entities}, LLM Extracted Relationships: {doc_specific_llm_extracted_relationships}")
        logger.info(f"💾 Document Summary: Actual New Graph Entities: {doc_specific_actual_entities_created}, Actual New Graph Relationships: {doc_specific_actual_relationships_created}")
        logger.info(f"⏱️ Total processing time for document: {processing_time:.2f} seconds.")
        
        # Log overall graph stats for context
        try:
            overall_stats = await graphiti_service.get_graph_stats()
            logger.info(f"ℹ️ Current overall graph stats: Nodes={overall_stats.get('node_count', 'N/A')}, Edges={overall_stats.get('edge_count', 'N/A')}")
        except Exception as e_stats:
            logger.warning(f"Could not retrieve overall graph stats at the end of document processing: {e_stats}")

        return KnowledgeGraphResult(
            success=final_success_status, # Reflects if all chunks were processed without hard errors
            entity_count=doc_specific_actual_entities_created, # Nodes created/merged for THIS document
            relationship_count=doc_specific_actual_relationships_created, # Edges created/merged for THIS document
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
    
    # Normalize whitespace: replace multiple spaces/tabs/newlines with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove page numbering lines like "--- Page X ---" or "- X -"
    text = re.sub(r'--- 第 \d+ 页 ---', '', text) # Specific to current format
    text = re.sub(r'-\s*\d+\s*-', '', text) # More generic page number
    
    # Remove lines that are mostly decorative (e.g., "********", "------")
    # This is a simple heuristic; more complex patterns might be needed
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove lines with many repeated non-alphanumeric characters
        if len(line) > 3 and len(set(line)) < 3 and not re.search(r'[a-zA-Z0-9\u4e00-\u9fff]', line):
            logger.debug(f"Removing decorative line: {line}")
            continue
        # Remove very short lines that are likely artifacts, unless they end with punctuation (might be intentional short sentences)
        if len(line.replace(" ","")) < 5 and not re.search(r'[。.!?？！]$', line):
             # Keep lines that look like list items (e.g., "1.", "a)")
            if not re.match(r'^\s*([(\d.)]|\w[.)])', line):
                logger.debug(f"Removing very short line: {line}")
                continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # Further remove excessive blank lines that might have been introduced or missed
    text = re.sub(r'\n\s*\n', '\n', text) # Replaces multiple newlines with a single one
    
    return text.strip()

def _split_text(text: str, max_chunk_size: int = 3000, overlap: int = 100) -> List[str]:
    """
    将长文本分割成较小的块，考虑句子边界和重叠。
    
    Args:
        text: 需要分割的文本.
        max_chunk_size: 每块的最大字符数.
        overlap: 块之间的重叠字符数，有助于保持上下文.
        
    Returns:
        List[str]: 分割后的文本块列表.
    """
    if not text:
        return []

    # Sentence terminators, including Chinese and English ones
    sentence_terminators = re.compile(r'(?<=[。.!?？！])\s+|(?<=\n)')

    paragraphs = text.split('\n\n') # Split by double newlines (paragraphs) first
    
    chunks = []
    current_chunk_text = ""

    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
        
        sentences = sentence_terminators.split(paragraph)
        sentences = [s.strip() for s in sentences if s and s.strip()]

        for sentence in sentences:
            if not sentence:
                continue
            if len(current_chunk_text) + len(sentence) + 1 <= max_chunk_size: # +1 for potential space
                if current_chunk_text:
                    current_chunk_text += " " + sentence
                else:
                    current_chunk_text = sentence
            else:
                # Chunk is full or sentence is too long
                if current_chunk_text: # Add current chunk
                    chunks.append(current_chunk_text.strip())

                # If sentence itself is larger than max_chunk_size, split it hard
                if len(sentence) > max_chunk_size:
                    for i in range(0, len(sentence), max_chunk_size - overlap):
                        chunks.append(sentence[i:i + max_chunk_size - overlap].strip())
                    current_chunk_text = "" # Reset
                else:
                    current_chunk_text = sentence # Start new chunk with current sentence

    if current_chunk_text: # Add any remaining text
        chunks.append(current_chunk_text.strip())

    # Apply overlap if not handled by sentence splitting logic for very long sentences
    # The current logic primarily splits by sentence then paragraph, then hard splits if a sentence is too long.
    # A more explicit overlap strategy might be needed if this isn't sufficient.
    # For now, the overlap parameter is mainly for the hard split case.
    # A simple post-processing overlap can be added if necessary:
    # if overlap > 0 and len(chunks) > 1:
    #     overlapped_chunks = [chunks[0]]
    #     for i in range(1, len(chunks)):
    #         prev_chunk_suffix = chunks[i-1][-overlap:]
    #         overlapped_chunks.append(prev_chunk_suffix.strip() + " " + chunks[i])
    #     return [c.strip() for c in overlapped_chunks if c.strip()]

    return [c.strip() for c in chunks if c.strip()]


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

async def create_neo4j_indexes_and_constraints(service: GraphitiService):
    """Creates necessary indexes and constraints in Neo4j if they don't exist."""
    if not service.is_available() or not service.client or not service.client.graph_db:
        logger.error("Cannot create Neo4j indexes/constraints: Graphiti service or DB driver not available.")
        return

    async with service.client.graph_db.session() as session:
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.uuid IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ep:Episodic) REQUIRE ep.uuid IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (ep:Episodic) ON (ep.name)",
        ]

        # Specific entity types from the LLM prompt
        entity_types = [
            "Material", "BridgeComponent", "ConstructionMethod", "DesignStandard",
            "Location", "Organization", "DamageType", "InspectionTechnique", "Permit",
            "Bridge", "BridgeSection", "Sensor", "MonitoringSystem", "Regulation", "Software",
            "EnvironmentalFactor", "LoadType", "GeotechnicalFeature"
        ]

        for entity_type in entity_types:
            safe_label = sanitize_label(entity_type) # Ensure label is safe
            if not safe_label.startswith("_"): # Avoid creating indexes on placeholder/error labels
                # Index for merging: e.g. MERGE (e:Entity:Material {name: $name, entity_type: "Material"})
                # An index on :Material(name) and :Material(entity_type) would be beneficial.
                # Since entity_type property will be the same for all nodes with :Material label,
                # an index on :Material(name) is the most important one for the MERGE.
                queries.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{safe_label}) ON (n.name)")
                queries.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{safe_label}) ON (n.entity_type)")


        logger.info("🚀 Attempting to create Neo4j indexes and constraints...")
        for query in queries:
            try:
                logger.debug(f"Executing Neo4j schema query: {query}")
                await session.run(query)
            except Exception as e:
                # Errors can happen if an index/constraint exists in a slightly different form
                # or due to concurrent modifications. Usually, "IF NOT EXISTS" handles most cases.
                logger.warning(f"⚠️ Could not execute Neo4j schema query '{query}': {e}")
        logger.info("✅ Neo4j indexes and constraints creation process completed.")


def reset_graphiti_service():
    """重置 Graphiti 服务（用于测试）"""
    global graphiti_service
    graphiti_service = None 