"""
查看知识图谱内容
展示 Ollama 生成的实体和关系
"""

import asyncio
from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

async def main():
    print("🔍 查看知识图谱内容...")
    
    try:
        # 配置 Ollama
        llm_config = LLMConfig(
            api_key="local-key",
            model="qwen2.5:7b",
            small_model="qwen2.5:7b",
            base_url="http://localhost:11434/v1",
        )
        
        embedder_config = OpenAIEmbedderConfig(
            api_key="local-key",
            embedding_model="nomic-embed-text",
            embedding_dim=768,
            base_url="http://localhost:11434/v1",
        )
        
        # 初始化 Graphiti
        graphiti = Graphiti(
            "bolt://localhost:7687",
            "neo4j", 
            "bridge123",
            llm_client=OpenAIClient(config=llm_config),
            embedder=OpenAIEmbedder(config=embedder_config),
        )
        
        print("✅ 连接成功")
        
        # 使用 Neo4j 驱动直接查询数据
        driver = graphiti.driver
        
        # 查询所有实体节点
        print("\n📊 查看生成的实体节点：")
        entities_query = """
        MATCH (n:Entity)
        WHERE n.group_id = 'bridge_test'
        RETURN n.name AS name, n.node_type AS type, n.summary AS summary
        ORDER BY n.name
        """
        
        async with driver.session(database="neo4j") as session:
            # 查询实体
            entities_result = await session.run(entities_query)
            entities = await entities_result.data()
            
            if entities:
                for i, entity in enumerate(entities, 1):
                    print(f"  {i}. 【{entity['type']}】{entity['name']}")
                    if entity['summary']:
                        print(f"     描述：{entity['summary']}")
                    print()
            else:
                print("  ❌ 未找到实体节点")
            
            # 查询关系
            print("🔗 查看生成的关系：")
            relationships_query = """
            MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
            WHERE a.group_id = 'bridge_test' AND b.group_id = 'bridge_test'
            RETURN a.name AS source, r.edge_type AS relation, b.name AS target, r.fact AS description
            ORDER BY a.name
            """
            
            relations_result = await session.run(relationships_query)
            relations = await relations_result.data()
            
            if relations:
                for i, rel in enumerate(relations, 1):
                    print(f"  {i}. {rel['source']} --[{rel['relation']}]--> {rel['target']}")
                    if rel['description']:
                        print(f"     事实：{rel['description']}")
                    print()
            else:
                print("  ❌ 未找到关系")
        
        print("🎯 Ollama AI 处理总结：")
        print(f"✅ 识别了 {len(entities)} 个实体")
        print(f"✅ 构建了 {len(relations)} 个关系")
        print("✅ 本地 AI 成功完成了知识抽取和图谱构建")
        
        print("\n🌐 查看图形化界面：")
        print("  1. 打开浏览器访问：http://localhost:7474")
        print("  2. 登录：neo4j / bridge123")
        print("  3. 运行查询：MATCH (n:Entity {group_id: 'bridge_test'})-[r]-(m) RETURN n,r,m")
        
    except Exception as e:
        print(f"❌ 错误：{str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 