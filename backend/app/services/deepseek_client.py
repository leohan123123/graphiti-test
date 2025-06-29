#!/usr/bin/env python3
"""
自定义 DeepSeek 客户端，兼容 Graphiti
"""

import json
import logging
import tiktoken
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel
from openai import AsyncOpenAI
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig

logger = logging.getLogger(__name__)

class DeepSeekClient(OpenAIClient):
    """自定义 DeepSeek 客户端，兼容 Graphiti"""
    
    def __init__(self, config: LLMConfig):
        # 初始化父类
        super().__init__(config)
        
        # 重新创建客户端，使用 DeepSeek 配置
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        self.config = config
        
        # 初始化 tokenizer 用于计算 token 数量
        try:
            self.tokenizer = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # DeepSeek 的限制
        self.MAX_CONTEXT_LENGTH = 65536  # DeepSeek 最大上下文长度
        self.RESERVED_TOKENS = 2000      # 为响应预留的 token 数量
        self.MAX_INPUT_TOKENS = self.MAX_CONTEXT_LENGTH - self.RESERVED_TOKENS
        
        logger.info(f"✅ DeepSeek 客户端初始化成功: {config.model}")
    
    def _count_tokens(self, text: str) -> int:
        """计算文本的 token 数量"""
        try:
            return len(self.tokenizer.encode(text))
        except:
            # 如果编码失败，使用粗略估计：1 token ≈ 4 字符
            return len(text) // 4
    
    def _count_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """计算消息列表的总 token 数量"""
        total_tokens = 0
        for message in messages:
            # 计算消息结构的开销
            total_tokens += 4  # role 和 content 字段的开销
            total_tokens += self._count_tokens(message.get("content", ""))
            total_tokens += self._count_tokens(message.get("role", ""))
        total_tokens += 2  # 对话结束标记
        return total_tokens
    
    def _truncate_messages(self, messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """截断消息以适应 token 限制"""
        if not messages:
            return messages
        
        # 保留系统消息（通常是第一条）
        truncated_messages = []
        system_message = None
        user_messages = []
        
        for message in messages:
            if message.get("role") == "system":
                system_message = message
            else:
                user_messages.append(message)
        
        # 计算系统消息的 token 数
        system_tokens = 0
        if system_message:
            system_tokens = self._count_tokens(system_message.get("content", "")) + 4
            truncated_messages.append(system_message)
        
        # 为用户消息分配剩余的 token
        remaining_tokens = max_tokens - system_tokens
        
        # 从最新的消息开始，逐步添加直到达到限制
        current_tokens = 0
        for message in reversed(user_messages):
            message_tokens = self._count_tokens(message.get("content", "")) + 4
            
            if current_tokens + message_tokens <= remaining_tokens:
                truncated_messages.insert(-1 if system_message else 0, message)
                current_tokens += message_tokens
            else:
                # 如果单条消息太长，尝试截断内容
                if len(truncated_messages) == (1 if system_message else 0):
                    # 这是第一条用户消息，必须包含一些内容
                    available_tokens = remaining_tokens - 4  # 减去消息结构开销
                    if available_tokens > 100:  # 至少保留100个token
                        content = message.get("content", "")
                        # 粗略估计：1 token ≈ 4 字符
                        max_chars = available_tokens * 4
                        if len(content) > max_chars:
                            # 从中间截断，保留开头和结尾
                            keep_start = max_chars // 3
                            keep_end = max_chars // 3
                            truncated_content = content[:keep_start] + "\n...[内容被截断]...\n" + content[-keep_end:]
                            truncated_message = {**message, "content": truncated_content}
                            truncated_messages.insert(-1 if system_message else 0, truncated_message)
                break
        
        logger.info(f"消息截断: 原始 {len(messages)} 条 -> 截断后 {len(truncated_messages)} 条")
        return truncated_messages
    
    async def _create_structured_completion(
        self,
        messages: List[Dict[str, Any]],
        response_model: Type[BaseModel],
        **kwargs
    ) -> BaseModel:
        """重写结构化完成方法，使用标准 JSON 模式而不是 beta API"""
        try:
            # 添加系统提示，要求以 JSON 格式返回
            json_schema = response_model.model_json_schema()
            system_prompt = f"""
请严格按照以下 JSON Schema 格式返回结果，不要包含任何其他文本：

Schema:
{json.dumps(json_schema, indent=2, ensure_ascii=False)}

要求：
1. 返回有效的 JSON 格式
2. 严格遵循 schema 结构
3. 不要添加任何解释或其他文本
4. 确保所有必需字段都存在
5. 如果没有找到相关内容，返回空数组而不是省略字段
"""
            
            # 修改消息，添加系统提示
            modified_messages = [
                {"role": "system", "content": system_prompt}
            ] + messages
            
            # 检查并截断消息以适应 token 限制
            total_tokens = self._count_messages_tokens(modified_messages)
            logger.info(f"请求 token 数量: {total_tokens}")
            
            if total_tokens > self.MAX_INPUT_TOKENS:
                logger.warning(f"Token 数量超限 ({total_tokens} > {self.MAX_INPUT_TOKENS})，开始截断...")
                modified_messages = self._truncate_messages(modified_messages, self.MAX_INPUT_TOKENS)
                final_tokens = self._count_messages_tokens(modified_messages)
                logger.info(f"截断后 token 数量: {final_tokens}")
            
            # 限制max_tokens在DeepSeek允许的范围内
            max_tokens = kwargs.get("max_tokens", 2000)
            if max_tokens and max_tokens > 8192:
                max_tokens = 8192
            elif max_tokens and max_tokens < 1:
                max_tokens = 1000
            
            # 使用标准的 chat completions API
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=modified_messages,
                response_format={"type": "json_object"},
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=max_tokens
            )
            
            # 解析响应
            content = response.choices[0].message.content
            logger.debug(f"DeepSeek 原始响应: {content}")
            
            try:
                # 尝试解析 JSON
                json_data = json.loads(content)
                
                # 验证必需字段并提供默认值
                schema_properties = json_schema.get("properties", {})
                required_fields = json_schema.get("required", [])
                
                for field in required_fields:
                    if field not in json_data:
                        # 根据字段类型提供默认值
                        field_schema = schema_properties.get(field, {})
                        field_type = field_schema.get("type", "string")
                        
                        if field_type == "array":
                            json_data[field] = []
                        elif field_type == "object":
                            json_data[field] = {}
                        elif field_type == "string":
                            json_data[field] = ""
                        elif field_type == "number":
                            json_data[field] = 0
                        elif field_type == "boolean":
                            json_data[field] = False
                        else:
                            json_data[field] = None
                
                # 创建 Pydantic 模型实例
                result = response_model(**json_data)
                logger.debug(f"解析成功: {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {e}, 内容: {content}")
                # 如果 JSON 解析失败，尝试提取 JSON 部分
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        json_data = json.loads(json_match.group())
                        
                        # 同样验证必需字段
                        schema_properties = json_schema.get("properties", {})
                        required_fields = json_schema.get("required", [])
                        
                        for field in required_fields:
                            if field not in json_data:
                                field_schema = schema_properties.get(field, {})
                                field_type = field_schema.get("type", "string")
                                
                                if field_type == "array":
                                    json_data[field] = []
                                elif field_type == "object":
                                    json_data[field] = {}
                                else:
                                    json_data[field] = ""
                        
                        result = response_model(**json_data)
                        logger.debug(f"提取 JSON 成功: {result}")
                        return result
                    except Exception as parse_error:
                        logger.error(f"提取的JSON解析也失败: {parse_error}")
                
                # 如果仍然失败，创建带有默认值的实例
                logger.warning(f"使用默认值创建 {response_model.__name__}")
                default_data = {}
                schema_properties = json_schema.get("properties", {})
                required_fields = json_schema.get("required", [])
                
                for field in required_fields:
                    field_schema = schema_properties.get(field, {})
                    field_type = field_schema.get("type", "string")
                    
                    if field_type == "array":
                        default_data[field] = []
                    elif field_type == "object":
                        default_data[field] = {}
                    else:
                        default_data[field] = ""
                
                return response_model(**default_data)
                
        except Exception as e:
            logger.error(f"DeepSeek 结构化完成失败: {e}")
            # 返回带有默认值的实例
            try:
                json_schema = response_model.model_json_schema()
                default_data = {}
                schema_properties = json_schema.get("properties", {})
                required_fields = json_schema.get("required", [])
                
                for field in required_fields:
                    field_schema = schema_properties.get(field, {})
                    field_type = field_schema.get("type", "string")
                    
                    if field_type == "array":
                        default_data[field] = []
                    elif field_type == "object":
                        default_data[field] = {}
                    else:
                        default_data[field] = ""
                
                return response_model(**default_data)
            except:
                return response_model()
    
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        response_model: Optional[Type[BaseModel]] = None,
        max_tokens: Optional[int] = None,
        model_size = None
    ) -> Dict[str, Any]:
        """生成响应 - 返回字典格式以匹配Graphiti期望"""
        if response_model:
            # 结构化响应，返回字典格式
            pydantic_result = await self._create_structured_completion(
                messages, response_model, max_tokens=max_tokens
            )
            # 将Pydantic模型转换为字典
            return pydantic_result.model_dump()
        else:
            # 标准文本生成 - 也需要检查 token 限制
            total_tokens = self._count_messages_tokens(messages)
            if total_tokens > self.MAX_INPUT_TOKENS:
                logger.warning(f"标准生成 Token 数量超限，开始截断...")
                messages = self._truncate_messages(messages, self.MAX_INPUT_TOKENS)
            
            max_tokens = max_tokens or 1000
            if max_tokens > 8192:
                max_tokens = 8192
            
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens
            )
            return {"content": response.choices[0].message.content}