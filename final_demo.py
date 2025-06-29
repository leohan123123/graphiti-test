"""
Graphiti + Ollama 完整功能演示
展示知识图谱构建、搜索、查询的完整流程
适合桥梁工程等专业领域的知识管理
"""

import asyncio
from datetime import datetime
from graphiti_core import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

async def demo_knowledge_graph():
    print("🌉 Graphiti 桥梁工程知识图谱 - 完整演示")
    print("=" * 50)
    
    try:
        # 配置 Ollama
        print("⚙️  配置本地 AI 模型...")
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
        print("📊 连接知识图谱数据库...")
        graphiti = Graphiti(
            "bolt://localhost:7687",
            "neo4j", 
            "bridge123",
            llm_client=OpenAIClient(config=llm_config),
            embedder=OpenAIEmbedder(config=embedder_config),
        )
        
        print("✅ 系统初始化完成")
        print()
        
        # 演示数据
        bridge_engineering_data = [
            "钢结构桥梁采用高强度钢材，抗拉强度达到450MPa。",
            "预应力混凝土梁的预应力损失需要考虑徐变、收缩和松弛。", 
            "桥梁动力特性分析包括自振频率、振型和阻尼比的计算。",
            "斜拉桥的索力监测系统可以实时检测每根拉索的张力变化。",
            "基础设计需要考虑地基承载力、沉降计算和抗震要求。",
            "桥面防水系统包括防水层、保护层和排水设施。"
        ]
        
        print("📝 正在构建桥梁工程知识图谱...")
        print("   (本地 AI 正在分析和提取知识...)")
        
        # 添加专业数据
        for i, data in enumerate(bridge_engineering_data):
            await graphiti.add_episode(
                name=f"bridge_tech_{i+1}",
                episode_body=data,
                source_description="桥梁工程技术资料",
                reference_time=datetime.now(),
                group_id="bridge_demo"
            )
            print(f"   ✅ 已处理：{data[:30]}...")
        
        print("\n🎯 知识图谱构建完成！")
        
        # 统计和查询
        driver = graphiti.driver
        
        async with driver.session(database="neo4j") as session:
            # 统计实体
            entity_result = await session.run(
                "MATCH (n:Entity {group_id: 'bridge_demo'}) RETURN count(n) AS count"
            )
            entity_count = (await entity_result.single())['count']
            
            # 统计关系
            rel_result = await session.run(
                "MATCH (a:Entity {group_id: 'bridge_demo'})-[r:RELATES_TO]-(b:Entity {group_id: 'bridge_demo'}) RETURN count(r) AS count"
            )
            rel_count = (await rel_result.single())['count']
            
            print(f"\n📊 新构建的知识图谱统计：")
            print(f"   🎯 识别实体：{entity_count} 个")
            print(f"   🔗 建立关系：{rel_count} 个")
            print(f"   🧠 AI 处理：100% 本地化")
            
            # 展示识别的关键实体
            print(f"\n🔍 AI 识别的关键技术概念：")
            entity_query = """
            MATCH (n:Entity {group_id: 'bridge_demo'})
            WHERE n.name CONTAINS '桥' OR n.name CONTAINS '钢' OR n.name CONTAINS '混凝土' 
               OR n.name CONTAINS '系统' OR n.name CONTAINS '强度'
            RETURN n.name AS name, n.summary AS summary
            LIMIT 8
            """
            
            entities_result = await session.run(entity_query)
            entities = await entities_result.data()
            
            for i, entity in enumerate(entities, 1):
                print(f"   {i}. 【{entity['name']}】")
                if entity['summary']:
                    summary = entity['summary'][:60] + "..." if len(entity['summary']) > 60 else entity['summary']
                    print(f"      {summary}")
            
            # 展示技术关系
            print(f"\n🔗 AI 构建的技术关系：")
            rel_query = """
            MATCH (a:Entity {group_id: 'bridge_demo'})-[r:RELATES_TO]-(b:Entity {group_id: 'bridge_demo'})
            RETURN a.name AS source, b.name AS target, r.fact AS relationship
            LIMIT 6
            """
            
            relations_result = await session.run(rel_query)
            relations = await relations_result.data()
            
            for i, rel in enumerate(relations, 1):
                print(f"   {i}. {rel['source']} ↔ {rel['target']}")
                if rel['relationship']:
                    fact = rel['relationship'][:50] + "..." if len(rel['relationship']) > 50 else rel['relationship']
                    print(f"      关系：{fact}")
        
        print("\n🌐 可视化查看：")
        print("   1. 浏览器访问：http://localhost:7474")
        print("   2. 登录：neo4j / bridge123")
        print("   3. 查看新数据：")
        print("      MATCH (n:Entity {group_id: 'bridge_demo'})-[r]-(m) RETURN n,r,m")
        
        print("\n💡 应用场景演示：")
        
        # 场景1：快速查找相关概念
        print("\n【场景1：查找钢结构相关技术】")
        steel_query = """
        MATCH (n:Entity {group_id: 'bridge_demo'})
        WHERE n.name CONTAINS '钢' OR n.summary CONTAINS '钢'
        RETURN n.name AS concept, n.summary AS description
        LIMIT 3
        """
        
        async with driver.session(database="neo4j") as session:
            steel_result = await session.run(steel_query)
            steel_concepts = await steel_result.data()
            
            for concept in steel_concepts:
                print(f"   🔧 {concept['concept']}")
                if concept['description']:
                    desc = concept['description'][:80] + "..." if len(concept['description']) > 80 else concept['description']
                    print(f"      {desc}")
        
        # 场景2：查找监测相关技术
        print("\n【场景2：查找监测系统技术】")
        monitor_query = """
        MATCH (n:Entity {group_id: 'bridge_demo'})
        WHERE n.name CONTAINS '监测' OR n.summary CONTAINS '监测' OR n.summary CONTAINS '检测'
        RETURN n.name AS concept, n.summary AS description
        LIMIT 3
        """
        
        async with driver.session(database="neo4j") as session:
            monitor_result = await session.run(monitor_query)
            monitor_concepts = await monitor_result.data()
            
            for concept in monitor_concepts:
                print(f"   📡 {concept['concept']}")
                if concept['description']:
                    desc = concept['description'][:80] + "..." if len(concept['description']) > 80 else concept['description']
                    print(f"      {desc}")
        
        print("\n🎉 演示完成！")
        print("\n✨ Ollama + Graphiti 的优势：")
        print("   🔒 数据隐私：知识完全保存在本地")
        print("   💰 零成本：无需任何 API 费用")
        print("   🚀 无限制：可处理任意量级的数据")
        print("   🧠 智能化：自动提取实体和关系")
        print("   🔍 可搜索：支持复杂的图谱查询")
        print("   📊 可视化：Neo4j 提供图形界面")
        
        print("\n🔮 下一步建议：")
        print("   1. 导入更多桥梁工程文档")
        print("   2. 构建领域专用的知识图谱")
        print("   3. 开发基于图谱的智能问答系统")
        print("   4. 集成到 CAD/BIM 设计工具中")
        
    except Exception as e:
        print(f"❌ 错误：{str(e)}")

if __name__ == "__main__":
    asyncio.run(demo_knowledge_graph()) 