<script lang="ts">
	import { onMount } from 'svelte';
	import { Upload, Database, BarChart3, Download, ArrowRight, FileText, Activity, Zap } from 'lucide-svelte';
	
	// 统计数据状态
	let stats = $state([
		{ label: '已处理文档', value: '0', icon: FileText, color: 'text-blue-600' },
		{ label: '知识实体', value: '0', icon: Database, color: 'text-green-600' },
		{ label: '关系数量', value: '0', icon: Activity, color: 'text-purple-600' },
		{ label: '总文件数', value: '0', icon: Download, color: 'text-orange-600' }
	]);

	let loading = $state(true);
	let error = $state('');

	// 获取统计数据
	async function fetchStats() {
		try {
			loading = true;
			const response = await fetch('/api/v1/documents/stats');
			if (!response.ok) {
				throw new Error(`HTTP ${response.status}: ${response.statusText}`);
			}
			const data = await response.json();
			
			// 更新统计数据
			stats = [
				{ 
					label: '已处理文档', 
					value: data.processed_documents.toString(), 
					icon: FileText, 
					color: 'text-blue-600' 
				},
				{ 
					label: '知识实体', 
					value: data.total_nodes.toString(), 
					icon: Database, 
					color: 'text-green-600' 
				},
				{ 
					label: '关系数量', 
					value: data.total_relations.toString(), 
					icon: Activity, 
					color: 'text-purple-600' 
				},
				{ 
					label: '总文件数', 
					value: data.total_documents.toString(), 
					icon: Download, 
					color: 'text-orange-600' 
				}
			];
			
			error = '';
			console.log('📊 统计数据已更新:', data);
		} catch (err) {
			console.error('获取统计数据失败:', err);
			error = '获取统计数据失败';
		} finally {
			loading = false;
		}
	}

	// 定期刷新数据
	let refreshInterval: number;

	onMount(() => {
		fetchStats();
		
		// 每30秒刷新一次数据
		refreshInterval = setInterval(fetchStats, 30000);
		
		// 清理函数
		return () => {
			if (refreshInterval) {
				clearInterval(refreshInterval);
			}
		};
	});
	
	const quickActions = [
		{
			title: '上传文档',
			description: '上传PDF、Word、CAD等工程文档',
			icon: Upload,
			href: '/upload',
			color: 'from-blue-500 to-blue-600'
		},
		{
			title: '浏览图谱',
			description: '探索知识图谱和实体关系',
			icon: Database,
			href: '/graph',
			color: 'from-green-500 to-green-600'
		},
		{
			title: '监控进度',
			description: '查看文档处理和图谱构建状态',
			icon: BarChart3,
			href: '/monitor',
			color: 'from-purple-500 to-purple-600'
		},
		{
			title: '导出数据',
			description: '导出训练语料和结构化数据',
			icon: Download,
			href: '/export',
			color: 'from-orange-500 to-orange-600'
		}
	];
</script>

<svelte:head>
	<title>桥梁知识图谱平台</title>
</svelte:head>

<div class="space-y-8">
	<!-- Hero Section -->
	<div class="text-center">
		<h1 class="text-4xl font-bold text-gray-900 mb-4">
			桥梁知识图谱平台
		</h1>
		<p class="text-xl text-gray-600 max-w-3xl mx-auto">
			基于AI技术的桥梁工程知识图谱构建平台，将非结构化工程文档转换为结构化知识图谱，为专业大模型训练提供高质量语料
		</p>
	</div>

	<!-- Stats Cards -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
		{#if loading}
			{#each [1, 2, 3, 4] as _}
				<div class="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
					<div class="flex items-center justify-between">
						<div class="flex-1">
							<div class="h-4 bg-gray-200 rounded w-24 mb-3"></div>
							<div class="h-8 bg-gray-200 rounded w-16"></div>
						</div>
						<div class="w-12 h-12 bg-gray-200 rounded-lg"></div>
					</div>
				</div>
			{/each}
		{:else if error}
			<div class="col-span-full bg-red-50 border border-red-200 rounded-xl p-6 text-center">
				<p class="text-red-600">⚠️ {error}</p>
				<button 
					onclick={fetchStats}
					class="mt-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
				>
					重新加载
				</button>
			</div>
		{:else}
			{#each stats as stat}
				{@const IconComponent = stat.icon}
				<div class="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-shadow duration-200">
					<div class="flex items-center justify-between">
						<div>
							<p class="text-sm font-medium text-gray-600">{stat.label}</p>
							<p class="text-3xl font-bold text-gray-900 mt-2">{stat.value}</p>
						</div>
						<div class="p-3 rounded-lg bg-gray-50">
							<IconComponent class="w-6 h-6 {stat.color}" />
						</div>
					</div>
				</div>
			{/each}
		{/if}
	</div>

	<!-- Quick Actions -->
	<div class="bg-white rounded-xl border border-gray-200 p-8">
		<h2 class="text-2xl font-bold text-gray-900 mb-6">快速开始</h2>
		<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
			{#each quickActions as action}
				{@const IconComponent = action.icon}
				<a 
					href={action.href}
					class="group relative bg-gradient-to-r {action.color} p-6 rounded-xl text-white overflow-hidden hover:scale-105 transition-transform duration-200"
				>
					<div class="relative z-10">
						<div class="flex items-center justify-between mb-4">
							<IconComponent class="w-8 h-8" />
							<ArrowRight class="w-5 h-5 opacity-0 group-hover:opacity-100 transform translate-x-2 group-hover:translate-x-0 transition-all duration-200" />
						</div>
						<h3 class="text-xl font-semibold mb-2">{action.title}</h3>
						<p class="text-white/90">{action.description}</p>
					</div>
					<!-- Background Pattern -->
					<div class="absolute inset-0 bg-gradient-to-br from-white/10 to-transparent"></div>
				</a>
			{/each}
		</div>
	</div>

	<!-- Features Section -->
	<div class="bg-white rounded-xl border border-gray-200 p-8">
		<h2 class="text-2xl font-bold text-gray-900 mb-6">平台特色</h2>
		<div class="grid grid-cols-1 md:grid-cols-3 gap-8">
			<div class="text-center">
				<div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
					<Zap class="w-6 h-6 text-blue-600" />
				</div>
				<h3 class="text-lg font-semibold text-gray-900 mb-2">智能处理</h3>
				<p class="text-gray-600">基于本地AI模型自动提取实体和关系，无需人工标注</p>
			</div>
			<div class="text-center">
				<div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
					<Database class="w-6 h-6 text-green-600" />
				</div>
				<h3 class="text-lg font-semibold text-gray-900 mb-2">知识图谱</h3>
				<p class="text-gray-600">构建专业的桥梁工程知识图谱，支持复杂查询和推理</p>
			</div>
			<div class="text-center">
				<div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-4">
					<Activity class="w-6 h-6 text-purple-600" />
				</div>
				<h3 class="text-lg font-semibold text-gray-900 mb-2">数据安全</h3>
				<p class="text-gray-600">完全本地化部署，工程数据不外流，确保信息安全</p>
			</div>
		</div>
	</div>

	<!-- Getting Started -->
	<div class="bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl p-8 text-center">
		<h2 class="text-2xl font-bold text-gray-900 mb-4">开始使用</h2>
		<p class="text-gray-600 mb-6">
			上传您的第一个工程文档，体验AI驱动的知识图谱构建过程
		</p>
		<a 
			href="/upload"
			class="inline-flex items-center px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white font-medium rounded-lg hover:from-blue-700 hover:to-purple-700 transition-colors duration-200"
		>
			<Upload class="w-5 h-5 mr-2" />
			立即开始
		</a>
	</div>
</div>
