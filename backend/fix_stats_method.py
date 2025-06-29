import re

# 读取文件
with open('app/services/graphiti_service.py', 'r') as f:
    content = f.read()

# 定义新的 get_graph_stats 方法
new_method = '''    async def get_graph_stats(self) -> Dict[str, Any]:
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
                episode_result = session.run("MATCH (n:Episode) RETURN count(n) as episode_count")
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
            }'''

# 替换旧方法
pattern = r'    async def get_graph_stats\(self\) -> Dict\[str, Any\]:.*?(?=\n    def|\n# 全局实例|\nclass|\Z)'
new_content = re.sub(pattern, new_method, content, flags=re.DOTALL)

# 写回文件
with open('app/services/graphiti_service.py', 'w') as f:
    f.write(new_content)

print("✅ get_graph_stats 方法已修复")
