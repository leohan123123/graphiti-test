#!/bin/bash

echo "=== 桥梁工程知识图谱平台 - 系统监控 ==="
echo "时间: $(date)"
echo ""

# 检查服务状态
echo "🔍 检查服务状态..."
echo "后端服务 (8000端口):"
curl -s http://localhost:8000/ > /dev/null && echo "  ✅ 运行正常" || echo "  ❌ 服务异常"

echo "前端服务 (5173端口):"
curl -s http://localhost:5173/ > /dev/null && echo "  ✅ 运行正常" || echo "  ❌ 服务异常"

echo "Ollama服务 (11434端口):"
curl -s http://localhost:11434/api/tags > /dev/null && echo "  ✅ 运行正常" || echo "  ❌ 服务异常"

echo ""

# 检查知识图谱状态
echo "📊 知识图谱状态:"
GRAPH_HEALTH=$(curl -s http://localhost:8000/api/v1/knowledge/health)
echo "$GRAPH_HEALTH" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data['status'] == 'healthy':
        print('  ✅ Graphiti服务正常')
        print('  📦 Neo4j连接:', '✅ 正常' if data['neo4j_connected'] else '❌ 异常')
        print('  🤖 客户端可用:', '✅ 正常' if data['client_available'] else '❌ 异常')
    else:
        print('  ❌ Graphiti服务异常')
except:
    print('  ❌ 无法获取状态')
"

echo ""

# 检查知识图谱统计
echo "📈 知识图谱统计:"
GRAPH_STATS=$(curl -s http://localhost:8000/api/v1/knowledge/stats)
echo "$GRAPH_STATS" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'  📊 节点数量: {data[\"node_count\"]}')
    print(f'  🔗 边数量: {data[\"edge_count\"]}')
    print(f'  📝 对话数量: {data[\"episode_count\"]}')
except:
    print('  ❌ 无法获取统计信息')
"

echo ""

# 检查文档状态
echo "📄 文档处理状态:"
DOC_LIST=$(curl -s http://localhost:8000/api/v1/documents/list)
echo "$DOC_LIST" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    files = data['files']
    total = len(files)
    completed = len([f for f in files if f['status'] == 'completed'])
    uploaded = len([f for f in files if f['status'] == 'uploaded'])
    processing = len([f for f in files if f['status'] == 'processing'])
    failed = len([f for f in files if f['status'] == 'failed'])
    
    print(f'  📁 总文档数: {total}')
    print(f'  ✅ 已完成: {completed}')
    print(f'  ⏳ 待处理: {uploaded}')
    print(f'  🔄 处理中: {processing}')
    print(f'  ❌ 失败: {failed}')
    
    if total > 0:
        print(f'  📊 完成率: {completed/total*100:.1f}%')
        
    # 显示最近的文档
    if files:
        latest = sorted(files, key=lambda x: x['upload_time'], reverse=True)[:3]
        print('  📋 最近文档:')
        for f in latest:
            status_icon = {'completed': '✅', 'uploaded': '⏳', 'processing': '🔄', 'failed': '❌'}.get(f['status'], '❓')
            print(f'    {status_icon} {f[\"filename\"]} ({f[\"status\"]})')
except:
    print('  ❌ 无法获取文档信息')
"

echo ""
echo "=== 监控完成 ===" 