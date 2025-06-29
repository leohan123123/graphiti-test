#!/usr/bin/env python3
"""修复 Graphiti 初始化方法"""

def fix_graphiti_init():
    file_path = "app/services/graphiti_service.py"
    
    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换错误的初始化方法
    old_method = '''            # 方式2：如果有OpenAI API Key，使用完整配置
            if os.environ.get("OPENAI_API_KEY"):
                try:
                    self.client = Graphiti(
                        uri="bolt://localhost:7687",
                        user="neo4j", 
                        password="bridge123",
                        llm_config={
                            "provider": "openai",
                            "model": "gpt-3.5-turbo"
                        }
                    )
                    logger.info("✅ Graphiti 客户端初始化成功（方式2）")
                    return
                except Exception as e2:
                    logger.warning(f"⚠️ 方式2初始化失败: {e2}")
            
            # 方式3：使用本地Ollama
            try:
                self.client = Graphiti(
                    uri="bolt://localhost:7687",
                    user="neo4j", 
                    password="bridge123",
                    llm_config={
                        "provider": "ollama",
                        "model": "qwen2.5:7b",
                        "base_url": "http://localhost:11434"
                    }
                )
                logger.info("✅ Graphiti 客户端初始化成功（方式3 - Ollama）")
                return
            except Exception as e3:
                logger.warning(f"⚠️ 方式3初始化失败: {e3}")'''
    
    new_method = '''            # 方式2：如果有OpenAI API Key，使用OpenAI客户端
            if os.environ.get("OPENAI_API_KEY"):
                try:
                    from graphiti_core.llm_client.openai_client import OpenAIClient
                    from graphiti_core.llm_client.config import LLMConfig
                    
                    llm_config = LLMConfig(
                        api_key=os.environ.get("OPENAI_API_KEY"),
                        model="gpt-3.5-turbo"
                    )
                    llm_client = OpenAIClient(config=llm_config)
                    
                    self.client = Graphiti(
                        uri="bolt://localhost:7687",
                        user="neo4j", 
                        password="bridge123",
                        llm_client=llm_client
                    )
                    logger.info("✅ Graphiti 客户端初始化成功（使用OpenAI）")
                    return
                except Exception as e2:
                    logger.warning(f"⚠️ OpenAI初始化失败: {e2}")
            
            # 方式3：使用本地Ollama
            try:
                from graphiti_core.llm_client.openai_client import OpenAIClient
                from graphiti_core.llm_client.config import LLMConfig
                
                llm_config = LLMConfig(
                    api_key="local-key",
                    model="qwen2.5:7b",
                    base_url="http://localhost:11434/v1"
                )
                llm_client = OpenAIClient(config=llm_config)
                
                self.client = Graphiti(
                    uri="bolt://localhost:7687",
                    user="neo4j", 
                    password="bridge123",
                    llm_client=llm_client
                )
                logger.info("✅ Graphiti 客户端初始化成功（使用Ollama）")
                return
            except Exception as e3:
                logger.warning(f"⚠️ Ollama初始化失败: {e3}")'''
    
    # 替换内容
    if old_method in content:
        content = content.replace(old_method, new_method)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Graphiti 初始化方法已修复")
    else:
        print("❌ 未找到要替换的内容")

if __name__ == "__main__":
    fix_graphiti_init()
