<script lang="ts">
	import { onMount } from 'svelte';
	import { Search, Filter, Maximize2, Download, RefreshCw, Settings, FileText, Trash2, Eye, Zap } from 'lucide-svelte';
	import KnowledgeGraph from '$lib/components/KnowledgeGraph.svelte';
	import type { ElementDefinition } from 'cytoscape';
	
	let graphContainer: HTMLDivElement; // This might not be needed if KnowledgeGraph handles its own container
	let searchQuery = $state('');
	let selectedNodeInfo: any = $state(null); // For displaying details of node clicked in graph or search
	let isLoading = $state(true); // Start with loading true
	let searchResults = $state<any[]>([]);
	let selectedDocumentId = $state<string | null>(null);
	
	// Cytoscape elements
	let graphElements = $state<ElementDefinition[]>([]);

	// Raw graph data from API, to be transformed
	let rawGraphData = $state<{ nodes: any[], edges: any[] }>({
		nodes: [],
		edges: []
	});
	
	let nodeTypes = $state<Array<{type: string, label: string, color: string, count: number}>>([
		// Default/fallback node types
		{ type: 'concept', label: '概念', color: '#3B82F6', count: 0 },
		{ type: 'material', label: '材料', color: '#10B981', count: 0 },
		{ type: 'component', label: '构件', color: '#F59E0B', count: 0 },
		{ type: 'type', label: '类型', color: '#8B5CF6', count: 0 },
		{ type: 'property', label: '属性', color: '#EF4444', count: 0 }
	]);
	let graphStats = $state({
		totalNodes: 0,
		totalRelations: 0,
		connectedComponents: 0
	});

	// 文档管理相关状态
	let documents = $state<Array<{
		file_id: string,
		filename: string,
		status: string,
		node_count: number,
		upload_time: number,
		processed_at?: number,
		file_type: string,
		file_size: number,
		error_message?: string
	}>>([]);

	// 获取文档列表
	async function fetchDocuments() {
		try {
			const response = await fetch('/api/v1/documents/list');
			if (response.ok) {
				const data = await response.json();
				documents = data.files || [];
				console.log('文档列表已更新:', documents);
			}
		} catch (error) {
			console.error('获取文档列表失败:', error);
		}
	}

	// 过滤文档显示特定文档的知识图谱
	async function filterByDocument(documentId: string | null) {
		selectedDocumentId = documentId;
		if (documentId) {
			// 这里可以调用API获取特定文档的知识图谱数据
			console.log('显示文档知识图谱:', documentId);
		} else {
			// 显示全部知识图谱
			await fetchGraphData();
		}
	}

	// 删除文档
	async function deleteDocument(documentId: string) {
		if (!confirm('确定要删除这个文档吗？这将同时删除相关的知识图谱数据。')) {
			return;
		}
		
		try {
			const response = await fetch(`/api/v1/documents/${documentId}`, {
				method: 'DELETE'
			});
			
			if (response.ok) {
				await fetchDocuments(); // 重新加载文档列表
				await fetchGraphData(); // 重新加载图谱数据
				if (selectedDocumentId === documentId) {
					selectedDocumentId = null;
				}
			}
		} catch (error) {
			console.error('删除文档失败:', error);
		}
	}

	// 获取知识图谱数据
	async function fetchGraphData() {
		try {
			isLoading = true;
			
			// 获取知识图谱健康状态和统计信息
			const healthResponse = await fetch('/api/v1/knowledge/health');
			if (healthResponse.ok) {
				const healthData = await healthResponse.json();
				
				if (healthData.graph_stats) {
					graphStats.totalNodes = healthData.graph_stats.nodes || 0;
					graphStats.totalRelations = healthData.graph_stats.relations || 0;
					graphStats.connectedComponents = healthData.graph_stats.components || 1;
				}
				
				// 如果有节点类型信息
				if (healthData.node_types && Array.isArray(healthData.node_types)) {
					nodeTypes = healthData.node_types;
				} else {
					// 默认节点类型
					nodeTypes = [
						{ type: 'concept', label: '概念', color: '#3B82F6', count: 0 },
						{ type: 'material', label: '材料', color: '#10B981', count: 0 },
						{ type: 'component', label: '构件', color: '#F59E0B', count: 0 },
						{ type: 'type', label: '类型', color: '#8B5CF6', count: 0 },
						{ type: 'property', label: '属性', color: '#EF4444', count: 0 }
					];
				}
				
				// 如果有图数据，更新图数据
				if (healthData.graph_data) {
					rawGraphData.nodes = healthData.graph_data.nodes || [];
					rawGraphData.edges = healthData.graph_data.edges || [];
					transformGraphData();
				} else {
					// Clear graph if no data
					rawGraphData.nodes = [];
					rawGraphData.edges = [];
					transformGraphData();
				}
			}
		} catch (error) {
			console.error('获取知识图谱数据失败:', error);
			rawGraphData.nodes = []; // Clear on error too
			rawGraphData.edges = [];
			transformGraphData();
		} finally {
			isLoading = false;
		}
	}

	function transformGraphData() {
		const newElements: ElementDefinition[] = [];
		rawGraphData.nodes.forEach(node => {
			newElements.push({
				group: 'nodes',
				data: {
					id: node.id || node.element_id, // Adapt based on actual API response
					label: node.properties?.name || node.properties?.label || node.id, // Adapt
					type: node.labels?.[0] || 'unknown', // Get first label as type
					properties: node.properties
				},
			});
		});
		rawGraphData.edges.forEach(edge => {
			newElements.push({
				group: 'edges',
				data: {
					id: edge.id || edge.element_id,
					source: edge.start_node_id || edge.source,
					target: edge.end_node_id || edge.target,
					label: edge.type || edge.label, // API might use 'type' or 'label' for relation type
					properties: edge.properties
				},
			});
		});
		graphElements = newElements;
	}
	
	let filterOptions = $state({
		showConcepts: true,
		showMaterials: true,
		showComponents: true,
		showTypes: true,
		showProperties: true
	});
	
	async function handleSearch() {
		if (!searchQuery.trim()) {
			searchResults = []; // Clear results if search query is empty
			return;
		}
		
		isLoading = true;
		try {
			const response = await fetch('/api/v1/knowledge/search', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ query: searchQuery, limit: 20 })
			});
			
			if (response.ok) {
				const result = await response.json();
				// Assuming result.entities is an array of nodes like those in rawGraphData.nodes
				searchResults = (result.entities || []).map((entity: any) => ({
					id: entity.id || entity.element_id,
					label: entity.properties?.name || entity.properties?.label || entity.id,
					type: entity.labels?.[0] || 'unknown',
					properties: entity.properties
				}));
				console.log('搜索结果:', searchResults);
			} else {
				searchResults = [];
				console.error('搜索API错误:', response.status, await response.text());
			}
		} catch (error) {
			searchResults = [];
			console.error('搜索失败:', error);
		} finally {
			isLoading = false;
		}
	}

	function handleSearchResultClick(node: any) {
		selectedNodeInfo = node; // Display node info
		// Future: Add interaction with KnowledgeGraph component to highlight/center this node
		// e.g., by calling a method on the component instance or binding a prop
		console.log('Search result clicked:', node);
		// Example: if KnowledgeGraph component has a method `centerOnNode(nodeId)`
		// knowledgeGraphInstance?.centerOnNode(node.id);
	}

	function handleNodeClickFromGraph(event: CustomEvent) {
		const nodeData = event.detail.node;
		selectedNodeInfo = {
			id: nodeData.id,
			label: nodeData.label,
			type: nodeData.type,
			properties: nodeData.properties
			// Add other relevant details from nodeData as needed
		};
		console.log('Node clicked in graph:', selectedNodeInfo);
	}
	
	function resetGraph() {
		selectedDocumentId = null;
		searchQuery = '';
		searchResults = [];
		selectedNodeInfo = null;
		fetchGraphData(); // This will refetch and transform data
		console.log('Resetting graph view');
	}
	
	function exportGraph() {
		console.log('Exporting graph');
		// This would likely involve taking `rawGraphData` or `graphElements`
		// and formatting them (e.g., as JSON, CSV, GraphML) then triggering a download.
		// Placeholder for now.
	}
	
	let knowledgeGraphInstance: KnowledgeGraph; // To call methods on the component if needed

	function toggleFullscreen() {
		const graphElement = document.querySelector('#graph-visualization-area'); // Target the graph area
		if (graphElement) {
			if (!document.fullscreenElement) {
				graphElement.requestFullscreen().catch(err => {
					alert(`全屏模式错误: ${err.message} (${err.name})`);
				});
			} else {
				document.exitFullscreen();
			}
		}
	}

	// 格式化文件大小
	function formatFileSize(bytes: number): string {
		if (bytes === 0) return '0 B';
		const k = 1024;
		const sizes = ['B', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}

	// 格式化时间
	function formatDate(dateString: string): string {
		return new Date(dateString).toLocaleString('zh-CN');
	}

	// 获取状态颜色
	function getStatusColor(status: string): string {
		switch (status) {
			case 'completed': return 'text-green-600 bg-green-100';
			case 'processing': return 'text-yellow-600 bg-yellow-100';
			case 'failed': return 'text-red-600 bg-red-100';
			default: return 'text-gray-600 bg-gray-100';
		}
	}

	// 获取状态文本
	function getStatusText(status: string): string {
		switch (status) {
			case 'completed': return '已完成';
			case 'processing': return '处理中';
			case 'failed': return '失败';
			default: return '未知';
		}
	}
	
	onMount(() => {
		// 加载真实的知识图谱数据和文档列表
		fetchGraphData();
		fetchDocuments();
		console.log('Initializing graph visualization');
	});
</script>

<svelte:head>
	<title>知识图谱 - 桥梁知识图谱平台</title>
</svelte:head>

<div class="md:h-[calc(100vh-8rem)] flex flex-col md:flex-row gap-6">
	<!-- 左侧控制面板 -->
	<div class="w-full md:w-80 bg-white rounded-xl border border-gray-200 p-6 overflow-y-auto md:h-full shrink-0"> {{!-- Added shrink-0 for md+ --}}
		<!-- 搜索 -->
		<div class="mb-6">
			<h3 class="text-lg font-semibold text-gray-900 mb-3">搜索图谱</h3>
			<div class="relative">
				<Search class="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
				<input
					bind:value={searchQuery}
					type="text"
					placeholder="搜索实体、关系..."
					class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
					onkeypress={(e) => e.key === 'Enter' && handleSearch()}
				/>
			</div>
			<button
				onclick={handleSearch}
				class="w-full mt-2 px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors duration-200"
			>
				搜索
			</button>

			<!-- Search Results -->
			{#if searchResults.length > 0}
				<div class="mt-4 border-t border-gray-200 pt-4 max-h-60 overflow-y-auto">
					<h4 class="text-sm font-semibold text-gray-700 mb-2">搜索结果 ({searchResults.length})</h4>
					<ul class="space-y-1">
						{#each searchResults as result (result.id)}
							<li>
								<button
									onclick={() => handleSearchResultClick(result)}
									class="w-full text-left p-2 rounded-md hover:bg-gray-100 focus:outline-none focus:bg-gray-100 transition-colors duration-150"
								>
									<div class="text-sm font-medium text-blue-600 truncate">{result.label}</div>
									<div class="text-xs text-gray-500">{result.type}</div>
								</button>
							</li>
						{/each}
					</ul>
				</div>
			{:else if isLoading && searchQuery.trim()}
				<div class="mt-4 text-center text-sm text-gray-500">正在搜索...</div>
			{/if}
		</div>

		<!-- 文档管理 -->
		<div class="mb-6">
			<h3 class="text-lg font-semibold text-gray-900 mb-3 flex items-center">
				<FileText class="w-4 h-4 mr-2" />
				文档管理
			</h3>
			
			<!-- 显示所有文档按钮 -->
			<button
				onclick={() => filterByDocument(null)}
				class="w-full mb-3 px-4 py-2 text-sm {selectedDocumentId === null ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'} font-medium rounded-lg transition-colors duration-200"
			>
				显示全部图谱
			</button>
			
			<div class="space-y-2 max-h-48 overflow-y-auto">
				{#each documents as doc}
					<div class="border border-gray-200 rounded-lg p-3 {selectedDocumentId === doc.file_id ? 'bg-blue-50 border-blue-200' : ''}">
						<div class="flex items-start justify-between">
							<div class="flex-1 min-w-0">
								<h4 class="text-sm font-medium text-gray-900 truncate" title={doc.filename}>
									{doc.filename}
								</h4>
								<div class="mt-1 flex items-center space-x-2">
									<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium {getStatusColor(doc.status)}">
										{getStatusText(doc.status)}
									</span>
									{#if doc.node_count > 0}
										<span class="text-xs text-gray-500">
											{doc.node_count} 节点
										</span>
									{/if}
								</div>
								<div class="mt-1 text-xs text-gray-500">
									{new Date(doc.upload_time * 1000).toLocaleString('zh-CN')}
								</div>
							</div>
							<div class="flex space-x-1 ml-2">
								<button
									onclick={() => filterByDocument(doc.file_id)}
									class="p-1 text-gray-400 hover:text-blue-600 transition-colors"
									title="查看此文档的知识图谱"
								>
									<Eye class="w-3 h-3" />
								</button>
								<button
									onclick={() => deleteDocument(doc.file_id)}
									class="p-1 text-gray-400 hover:text-red-600 transition-colors"
									title="删除文档"
								>
									<Trash2 class="w-3 h-3" />
								</button>
							</div>
						</div>
					</div>
				{/each}
				
				{#if documents.length === 0}
					<div class="text-center py-4 text-gray-500 text-sm">
						暂无文档
					</div>
				{/if}
			</div>
		</div>

		<!-- 节点类型过滤 -->
		<div class="mb-6">
			<h3 class="text-lg font-semibold text-gray-900 mb-3 flex items-center">
				<Filter class="w-4 h-4 mr-2" />
				节点类型
			</h3>
			<div class="space-y-3">
				{#each nodeTypes as nodeType}
					<label class="flex items-center">
						<input
							type="checkbox"
							checked={true}
							class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
						/>
						<div class="ml-3 flex items-center flex-1">
							<div 
								class="w-3 h-3 rounded-full mr-2"
								style="background-color: {nodeType.color}"
							></div>
							<span class="text-sm text-gray-700 flex-1">{nodeType.label}</span>
							<span class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
								{nodeType.count}
							</span>
						</div>
					</label>
				{/each}
			</div>
		</div>

		<!-- 图谱统计 -->
		<div class="mb-6">
			<h3 class="text-lg font-semibold text-gray-900 mb-3">图谱统计</h3>
			<div class="space-y-2 text-sm">
				<div class="flex justify-between">
					<span class="text-gray-600">总节点数</span>
					<span class="font-medium">{graphStats.totalNodes}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-gray-600">总关系数</span>
					<span class="font-medium">{graphStats.totalRelations}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-gray-600">连通分量</span>
					<span class="font-medium">{graphStats.connectedComponents}</span>
				</div>
			</div>
		</div>

		<!-- 选中节点信息 -->
		{#if selectedNodeInfo}
			<div class="mb-6">
				<h3 class="text-lg font-semibold text-gray-900 mb-3">节点详情</h3>
				<div class="bg-gray-50 rounded-lg p-4 text-sm space-y-2">
					<div>
						<span class="font-medium text-gray-700">名称:</span>
						<span class="text-gray-900 ml-1">{selectedNodeInfo.label || selectedNodeInfo.name || 'N/A'}</span>
					</div>
					<div>
						<span class="font-medium text-gray-700">类型:</span>
						<span class="text-gray-900 ml-1">{selectedNodeInfo.type || 'N/A'}</span>
					</div>
					{#if selectedNodeInfo.properties}
						<div class="pt-1 mt-1 border-t">
							<h5 class="font-medium text-gray-700 mb-1">属性:</h5>
							<ul class="space-y-1 max-h-32 overflow-y-auto">
								{#each Object.entries(selectedNodeInfo.properties) as [key, value]}
									<li class="text-xs">
										<span class="font-semibold text-gray-600">{key}:</span>
										<span class="text-gray-800 ml-1 truncate">{value}</span>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
					{#if !selectedNodeInfo.properties || Object.keys(selectedNodeInfo.properties).length === 0}
						<p class="text-xs text-gray-500">无更多属性信息。</p>
					{/if}
				</div>
			</div>
		{/if}

		<!-- 操作按钮 -->
		<div class="space-y-2">
			<button
				onclick={resetGraph}
				class="w-full flex items-center justify-center px-4 py-2 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 transition-colors duration-200"
			>
				<RefreshCw class="w-4 h-4 mr-2" />
				重置视图
			</button>
			<button
				onclick={exportGraph}
				class="w-full flex items-center justify-center px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors duration-200"
			>
				<Download class="w-4 h-4 mr-2" />
				导出图谱
			</button>
		</div>
	</div>

	<!-- 右侧图谱可视化区域 -->
	<div class="flex-1 bg-white rounded-xl border border-gray-200 relative overflow-hidden min-h-[400px] md:min-h-0"> {{!-- min-height for stacked view --}}
		<!-- 工具栏 -->
		<div class="absolute top-4 right-4 z-10 flex space-x-2">
			<button
				onclick={toggleFullscreen}
				class="p-2 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-white transition-colors duration-200"
				title="全屏"
			>
				<Maximize2 class="w-4 h-4" />
			</button>
			<button
				class="p-2 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-white transition-colors duration-200"
				title="设置"
			>
				<Settings class="w-4 h-4" />
			</button>
		</div>

		<!-- 图谱容器 -->
		<div id="graph-visualization-area" class="w-full h-full bg-gradient-to-br from-gray-50 to-white relative">
			{#if isLoading && graphElements.length === 0}
				<div class="absolute inset-0 flex flex-col items-center justify-center text-gray-500">
					<Zap class="w-12 h-12 mb-4 animate-pulse" />
					<p>正在加载图谱数据...</p>
				</div>
			{:else if !isLoading && graphElements.length === 0 && !selectedDocumentId}
				<div class="absolute inset-0 flex flex-col items-center justify-center text-gray-500 p-8 text-center">
					<Database class="w-12 h-12 mb-4 opacity-50" />
					<h3 class="text-xl font-semibold text-gray-700 mb-2">知识图谱为空</h3>
					<p class="max-w-md">
						当前没有可显示的全局知识图谱数据。请先 <a href="/upload" class="text-blue-600 hover:underline">上传并处理文档</a>，
						或从左侧选择一个已处理的文档来查看其对应的局部知识图谱。
					</p>
				</div>
			{:else if !isLoading && graphElements.length === 0 && selectedDocumentId}
				<div class="absolute inset-0 flex flex-col items-center justify-center text-gray-500 p-8 text-center">
					<FileText class="w-12 h-12 mb-4 opacity-50" />
					<h3 class="text-xl font-semibold text-gray-700 mb-2">文档图谱为空</h3>
					<p class="max-w-md">
						此文档尚未生成知识图谱数据，或者图谱数据为空。
						请确保文档已成功处理。
					</p>
				</div>
			{:else}
				<KnowledgeGraph
					bind:this={knowledgeGraphInstance}
					elements={graphElements}
					on:nodeclick={handleNodeClickFromGraph}
					class="w-full h-full"
				/>
				<!-- Legend -->
				<div class="absolute bottom-4 left-4 bg-white/80 backdrop-blur-sm p-3 rounded-lg border border-gray-200 shadow-md">
					<h4 class="text-xs font-semibold text-gray-700 mb-2">图例</h4>
					<ul class="space-y-1">
						{#each nodeTypes.filter(nt => graphElements.some(el => el.data.type === nt.type && el.group === 'nodes')).slice(0, 5) as type}
							<li class="flex items-center text-xs">
								<div class="w-2.5 h-2.5 rounded-full mr-1.5" style="background-color: {type.color}"></div>
								<span class="text-gray-600">{type.label}</span>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	</div>
</div> 