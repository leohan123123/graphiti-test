#!/usr/bin/env python3
"""
桥梁知识图谱平台 - 实时终端监控
显示文档处理进度和系统状态
"""

import os
import sys
import json
import time
import asyncio
import requests
from datetime import datetime
from typing import Dict, Any, List

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

class TerminalMonitor:
    """终端监控器"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000/api/v1"
        self.last_update = datetime.now()
        self.previous_docs = {}
        
    def clear_screen(self):
        """清屏"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def get_api_data(self, endpoint: str) -> Dict[str, Any]:
        """获取API数据"""
        try:
            response = requests.get(f"{self.api_base}{endpoint}", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def format_time(self, iso_time: str) -> str:
        """格式化时间"""
        try:
            dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
            return dt.strftime('%H:%M:%S')
        except:
            return "未知"
    
    def format_file_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def get_status_emoji(self, status: str) -> str:
        """获取状态表情"""
        status_map = {
            "uploaded": "📄",
            "processing": "⚙️",
            "completed": "✅",
            "failed": "❌"
        }
        return status_map.get(status, "❓")
    
    def display_header(self):
        """显示头部信息"""
        print("=" * 80)
        print("🌉 桥梁知识图谱平台 - 实时监控")
        print("=" * 80)
        print(f"⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔄 最后更新: {self.last_update.strftime('%H:%M:%S')}")
        print()
    
    def display_system_status(self):
        """显示系统状态"""
        print("📊 系统状态:")
        print("-" * 40)
        
        # 获取系统信息
        system_info = self.get_api_data("/info")
        if "error" not in system_info:
            print(f"🖥️  CPU使用率: {system_info.get('cpu_percent', 0):.1f}%")
            print(f"💾 内存使用率: {system_info.get('memory_percent', 0):.1f}%")
            print(f"💿 磁盘使用率: {system_info.get('disk_percent', 0):.1f}%")
        else:
            print(f"❌ 系统信息获取失败: {system_info['error']}")
        
        # 获取知识图谱状态
        kg_health = self.get_api_data("/knowledge/health")
        if "error" not in kg_health:
            status = kg_health.get('status', 'unknown')
            emoji = "✅" if status == "healthy" else "❌"
            print(f"{emoji} Graphiti状态: {status}")
            print(f"🗄️  Neo4j连接: {'✅' if kg_health.get('neo4j_connected') else '❌'}")
        else:
            print(f"❌ 知识图谱状态获取失败: {kg_health['error']}")
        
        print()
    
    def display_documents(self):
        """显示文档处理状态"""
        print("📁 文档处理状态:")
        print("-" * 80)
        
        docs_data = self.get_api_data("/documents/list")
        if "error" in docs_data:
            print(f"❌ 文档列表获取失败: {docs_data['error']}")
            return
        
        documents = docs_data.get("documents", [])
        if not documents:
            print("📭 暂无文档")
            return
        
        # 统计信息
        total = len(documents)
        uploaded = sum(1 for doc in documents if doc["status"] == "uploaded")
        processing = sum(1 for doc in documents if doc["status"] == "processing")
        completed = sum(1 for doc in documents if doc["status"] == "completed")
        failed = sum(1 for doc in documents if doc["status"] == "failed")
        
        print(f"📊 总计: {total} | 📄 待处理: {uploaded} | ⚙️ 处理中: {processing} | ✅ 完成: {completed} | ❌ 失败: {failed}")
        print()
        
        # 显示文档详情
        print(f"{'状态':<6} {'文件名':<30} {'类型':<6} {'大小':<10} {'上传时间':<10} {'节点数':<8}")
        print("-" * 80)
        
        for doc in documents:
            status_emoji = self.get_status_emoji(doc["status"])
            filename = doc["filename"][:28] + ".." if len(doc["filename"]) > 30 else doc["filename"]
            file_type = doc["file_type"].upper()
            file_size = self.format_file_size(doc["file_size"])
            upload_time = self.format_time(doc["upload_time"])
            node_count = doc.get("node_count", 0)
            
            print(f"{status_emoji:<6} {filename:<30} {file_type:<6} {file_size:<10} {upload_time:<10} {node_count:<8}")
            
            # 显示错误信息
            if doc["status"] == "failed" and doc.get("error_message"):
                print(f"       ❌ 错误: {doc['error_message']}")
            
            # 检查状态变化
            doc_id = doc["file_id"]
            if doc_id in self.previous_docs:
                prev_status = self.previous_docs[doc_id]["status"]
                curr_status = doc["status"]
                if prev_status != curr_status:
                    print(f"       🔄 状态变化: {prev_status} → {curr_status}")
        
        # 更新之前的文档状态
        self.previous_docs = {doc["file_id"]: doc for doc in documents}
        print()
    
    def display_knowledge_graph(self):
        """显示知识图谱统计"""
        print("🕸️ 知识图谱统计:")
        print("-" * 40)
        
        kg_stats = self.get_api_data("/knowledge/stats")
        if "error" not in kg_stats:
            node_count = kg_stats.get("node_count", 0)
            edge_count = kg_stats.get("edge_count", 0)
            episode_count = kg_stats.get("episode_count", 0)
            
            print(f"🔵 节点数量: {node_count}")
            print(f"🔗 边数量: {edge_count}")
            print(f"📖 文档片段: {episode_count}")
        else:
            print(f"❌ 知识图谱统计获取失败: {kg_stats['error']}")
        
        print()
    
    def display_recent_logs(self):
        """显示最近的日志"""
        print("📝 最近日志:")
        print("-" * 40)
        
        # 尝试读取日志文件
        log_files = ["monitor.log", "backend/app.log"]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        # 显示最后5行
                        for line in lines[-5:]:
                            line = line.strip()
                            if line:
                                # 截断过长的行
                                if len(line) > 75:
                                    line = line[:72] + "..."
                                print(f"   {line}")
                    break
                except Exception as e:
                    print(f"   ❌ 读取日志失败: {e}")
            else:
                print(f"   📭 日志文件不存在: {log_file}")
        
        print()
    
    def run_once(self):
        """运行一次监控"""
        self.clear_screen()
        self.display_header()
        self.display_system_status()
        self.display_documents()
        self.display_knowledge_graph()
        self.display_recent_logs()
        
        print("💡 提示: 按 Ctrl+C 退出监控")
        print("🔄 每5秒自动刷新...")
        
        self.last_update = datetime.now()
    
    def run(self):
        """运行监控循环"""
        print("🚀 启动桥梁知识图谱平台实时监控...")
        print("📡 连接到后端服务: http://localhost:8000")
        print()
        
        try:
            while True:
                self.run_once()
                time.sleep(5)  # 每5秒刷新一次
        except KeyboardInterrupt:
            print("\n\n👋 监控已停止")
        except Exception as e:
            print(f"\n\n❌ 监控出错: {e}")

def main():
    """主函数"""
    monitor = TerminalMonitor()
    monitor.run()

if __name__ == "__main__":
    main() 