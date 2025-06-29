#!/usr/bin/env python3
"""修复 Graphiti 服务使用 Ollama"""

def fix_graphiti_service():
    file_path = "app/services/graphiti_service.py"
    
    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换整个初始化方法
    old_method_start = "    def _initialize_client(self):"
    old_method_end = "            self.client = None"
    
    # 找到方法的开始和结束位置
    start_idx = content.find(old_method_start)
    if start_idx == -1:
        print("未找到 _initialize_client 方法")
        return False
    
    # 找到下一个方法的开始位置
    next_method_idx = content.find("\n    def ", start_idx + 1)
    if next_method_idx == -1:
        # 如果没有下一个方法，找到类的结束
        next_method_idx = len(content)
    
    # 新的方法实现
    new_method = '''    def _initialize_client(self):
        """初始化 Graphiti 客户端"""
        try:
            logger.info("🔧 正在初始化 Graphiti 客户端...")
            
            # 方式1：使用本地Ollama（优先）
            try:
                from graphiti_core.llm_client.openai_client import OpenAIClient
                from graphiti_core.llm_client.config import LLMConfig
                from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
                from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
                
                # 配置 Ollama LLM
                llm_config = LLMConfig(
                    api_key="local-key",
                    model="qwen2.5:7b",
                    base_url="http://localhost:11434/v1"
                )
                llm_client = OpenAIClient(config=llm_config)
                
                # 配置 Ollama 嵌入模型
                embedder_config = OpenAIEmbedderConfig(
                    api_key="local-key",
                    embedding_model="nomic-embed-text",
                    embedding_dim=768,
                    base_url="http://localhost:11434/v1"
                )
                embedder = OpenAIEmbedder(config=embedder_config)
                
                # 配置重排序器
                cross_encoder = OpenAIRerankerClient(config=llm_config)
                
                self.client = Graphiti(
                    uri="bolt://localhost:7687",
                    user="neo4j", 
                    password="bridge123",
                    llm_client=llm_client,
                    embedder=embedder,
                    cross_encoder=cross_encoder
                )
                logger.info("✅ Graphiti 客户端初始化成功（使用Ollama）")
                return
            except Exception as e1:
                logger.warning(f"⚠️ Ollama初始化失败: {e1}")
            
            # 方式2：最简单的初始化（备用）
            try:
                self.client = Graphiti(
                    uri="bolt://localhost:7687",
                    user="neo4j", 
                    password="bridge123"
                )
                logger.info("✅ Graphiti 客户端初始化成功（使用默认配置）")
                return
            except Exception as e2:
                logger.warning(f"⚠️ 默认初始化失败: {e2}")
            
            raise Exception("所有初始化方式都失败了")
            
        except Exception as e:
            logger.error(f"❌ Graphiti 客户端初始化失败: {e}")
            self.client = None

'''
    
    # 替换方法
    new_content = content[:start_idx] + new_method + content[next_method_idx:]
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Graphiti 服务已修复为使用 Ollama")
    return True

if __name__ == "__main__":
    fix_graphiti_service()
