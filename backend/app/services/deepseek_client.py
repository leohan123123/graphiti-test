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
        # 根据 DeepSeek 官方文档 (通常 deepseek-chat 为 32k context, 8k output completion)
        self.MAX_CONTEXT_LENGTH = 32768  # DeepSeek deepseek-chat 模型最大上下文长度
        self.MAX_OUTPUT_TOKENS = 8192    # DeepSeek deepseek-chat 模型最大输出 token 数量
        self.RESERVED_TOKENS = self.MAX_OUTPUT_TOKENS # 为响应预留的 token 数量，确保有足够空间生成完整响应
        self.MAX_INPUT_TOKENS = self.MAX_CONTEXT_LENGTH - self.RESERVED_TOKENS # 最大输入 token 数量

        logger.info(
            f"DeepSeek Tokenizer: {self.tokenizer.name}. "
            f"Context Length: {self.MAX_CONTEXT_LENGTH}, "
            f"Max Output Tokens: {self.MAX_OUTPUT_TOKENS}, "
            f"Reserved for Output: {self.RESERVED_TOKENS}, "
            f"Max Input Tokens: {self.MAX_INPUT_TOKENS}"
        )
        
        # Log the API key being used (mask it for production logs if sensitive)
        api_key_to_log = config.api_key[:5] + "..." + config.api_key[-4:] if config.api_key and len(config.api_key) > 9 else "Not Set or Too Short"
        logger.info(f"✅ DeepSeek 客户端初始化: model={config.model}, base_url={config.base_url}, api_key_used={api_key_to_log}")
    
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
            # Default max_tokens for completion, can be overridden by kwargs
            default_completion_max_tokens = 2000
            max_tokens = kwargs.get("max_tokens", default_completion_max_tokens)

            if max_tokens and max_tokens > self.MAX_OUTPUT_TOKENS:
                logger.warning(f"Requested max_tokens ({max_tokens}) exceeds model's MAX_OUTPUT_TOKENS ({self.MAX_OUTPUT_TOKENS}). Clamping to {self.MAX_OUTPUT_TOKENS}.")
                max_tokens = self.MAX_OUTPUT_TOKENS
            elif max_tokens and max_tokens < 1: # Ensure at least some tokens are requested for output
                logger.warning(f"Requested max_tokens ({max_tokens}) is invalid. Setting to a minimum of 100.")
                max_tokens = 100 # A small reasonable minimum
            
            # 使用标准的 chat completions API
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=modified_messages,
                response_format={"type": "json_object"},
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=max_tokens
            )
            
            # 解析响应
            api_content = None
            # Ensuring access via .content as per user's explicit instruction, though it was already the case.
            if response.choices and response.choices[0] and response.choices[0].message:
                api_content = response.choices[0].message.content # Explicitly using .content
                if api_content:
                    logger.debug(f"DeepSeek 原始响应: {api_content[:500]}...") # Log snippet
                else:
                    logger.warning("DeepSeek 响应消息内容为空.")
            else:
                logger.error("DeepSeek 响应无效、无有效选项或消息对象为空.")

            parsed_json_data = None
            if api_content:
                try:
                    # 尝试直接解析JSON
                    parsed_json_data = json.loads(api_content)
                except json.JSONDecodeError as e:
                    logger.warning(f"直接JSON解析失败: {e}. 尝试从内容中提取JSON.")
                    import re
                    # 尝试从 ```json ... ``` 或 ``` ... ``` 中提取
                    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", api_content, re.DOTALL)
                    if match:
                        extracted_json_str = match.group(1)
                        logger.info(f"从Markdown代码块中提取的JSON字符串: {extracted_json_str}")
                        try:
                            parsed_json_data = json.loads(extracted_json_str)
                            logger.info("从提取的JSON字符串解析成功.")
                        except json.JSONDecodeError as e_inner_md:
                            logger.error(f"从Markdown提取的JSON解析失败: {e_inner_md}")
                            parsed_json_data = None # Ensure it's None

                    if parsed_json_data is None: # If markdown extraction didn't work or wasn't applicable
                        # 尝试宽松的 regex 匹配 (原始的 r'\{.*\}')
                        json_match_loose = re.search(r'\{.*\}', api_content, re.DOTALL)
                        if json_match_loose:
                            logger.info(f"尝试使用宽松的 regex 进行JSON提取.")
                            try:
                                parsed_json_data = json.loads(json_match_loose.group(0))
                                logger.info("宽松的JSON提取和解析成功.")
                            except json.JSONDecodeError as e_inner_loose:
                                logger.error(f"宽松提取的JSON解析失败: {e_inner_loose}")
                                parsed_json_data = None # Ensure it's None
                            except Exception as e_gen_loose_inner:
                                logger.error(f"宽松提取的JSON解析时发生未知错误: {e_gen_loose_inner}")
                                parsed_json_data = None # Ensure it's None
                        else:
                            logger.warning("在响应中未找到宽松匹配的JSON格式子字符串.")
                except Exception as e_outer:
                    # Catch any other unexpected error during parsing attempts
                    logger.error(f"解析API内容时发生意外错误: {e_outer}")
                    parsed_json_data = None

            # 获取 schema 定义以备后用
            schema_properties = json_schema.get("properties", {})
            required_fields = json_schema.get("required", [])

            if parsed_json_data is not None:
                try:
                    # 验证必需字段并提供默认值
                    for field in required_fields:
                        if field not in parsed_json_data:
                            field_schema = schema_properties.get(field, {})
                            field_type = field_schema.get("type", "string")
                            # Provide default values based on type
                            if field_type == "array":
                                parsed_json_data[field] = []
                            elif field_type == "object":
                                parsed_json_data[field] = {}
                            elif field_type == "string":
                                parsed_json_data[field] = ""
                            elif field_type == "number":
                                parsed_json_data[field] = 0 # Or 0.0 if appropriate
                            elif field_type == "integer":
                                parsed_json_data[field] = 0
                            elif field_type == "boolean":
                                parsed_json_data[field] = False
                            else:
                                # For other types, or if type is not specified, use None
                                parsed_json_data[field] = None
                    
                    result = response_model(**parsed_json_data)
                    logger.debug(f"Pydantic 模型成功创建: {result}")
                    return result
                except Exception as e_pydantic:
                    logger.error(f"使用API响应创建Pydantic模型失败: {e_pydantic}. 将使用默认值.")
                    # Fall-through to default instantiation outside this block

            # 如果 parsed_json_data 为 None 或 Pydantic 模型创建失败，则使用默认值
            logger.warning(
                f"无法从API响应中解析JSON或创建模型失败. "
                f"将为 {response_model.__name__} 使用默认值."
            )
            default_data = {}
            for field in required_fields:
                field_schema = schema_properties.get(field, {})
                field_type = field_schema.get("type", "string")
                if field_type == "array":
                    default_data[field] = []
                elif field_type == "object":
                    default_data[field] = {}
                elif field_type == "string":
                    default_data[field] = ""
                elif field_type == "number":
                    default_data[field] = 0 # Or 0.0
                elif field_type == "integer":
                    default_data[field] = 0
                elif field_type == "boolean":
                    default_data[field] = False
                else:
                    default_data[field] = None

            # For any fields not in 'required' but in 'properties',
            # Pydantic will use their default values if defined in the model, or raise error if required and no default.
            # Our loop above only ensures 'required' fields get a basic default if missing from JSON.
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
                logger.warning(f"标准生成 Token 数量 ({total_tokens}) 超限 ({self.MAX_INPUT_TOKENS})，开始截断...")
                messages = self._truncate_messages(messages, self.MAX_INPUT_TOKENS)
                logger.info(f"标准生成截断后 token 数量: {self._count_messages_tokens(messages)}")
            
            # Use the provided max_tokens or a default, ensuring it's within model limits
            default_text_gen_max_tokens = 1000 # Default for standard text generation
            current_max_tokens = max_tokens if max_tokens is not None else default_text_gen_max_tokens

            if current_max_tokens > self.MAX_OUTPUT_TOKENS:
                logger.warning(f"Requested max_tokens ({current_max_tokens}) for standard generation exceeds model's MAX_OUTPUT_TOKENS ({self.MAX_OUTPUT_TOKENS}). Clamping to {self.MAX_OUTPUT_TOKENS}.")
                current_max_tokens = self.MAX_OUTPUT_TOKENS
            elif current_max_tokens < 1:
                logger.warning(f"Requested max_tokens ({current_max_tokens}) for standard generation is invalid. Setting to a minimum of 100.")
                current_max_tokens = 100 # A small reasonable minimum
            
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=0.7, # Default temperature for text generation
                    max_tokens=current_max_tokens
                )
                # Check if response and choices are valid before accessing content
                if response and response.choices and response.choices[0].message:
                    return {"content": response.choices[0].message.content}
                else:
                    logger.error("DeepSeek standard generation returned invalid response structure.")
                    return {"content": None, "error": "DeepSeek returned invalid response structure."}
            except Exception as e:
                logger.error(f"Error during DeepSeek standard generation: {e}", exc_info=True)
                return {"content": None, "error": str(e)}
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens
            )
            return {"content": response.choices[0].message.content}