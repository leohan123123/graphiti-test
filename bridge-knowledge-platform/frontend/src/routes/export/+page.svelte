<script lang="ts">
	import { onMount } from 'svelte';
	import { Download, FileText, Database, Package, CheckCircle, RefreshCw, AlertCircle } from 'lucide-svelte';
	
	interface ExportJob {
		id: string;
		name: string;
		type: 'knowledge_graph' | 'training_corpus' | 'full_dataset';
		format: string;
		status: 'pending' | 'processing' | 'completed' | 'failed';
		progress: number;
		createdAt: Date;
		fileSize?: string;
		downloadUrl?: string;
	}
	
	let selectedExportType = $state('training_corpus');
	let selectedFormat = $state('jsonl');
	let exportName = $state('');
	
	let exportJobs: ExportJob[] = $state([]);
	let isLoading = $state(false);

	// 获取导出历史
	async function fetchExportHistory() {
		try {
			const response = await fetch('/api/v1/export/list');
			if (response.ok) {
				const data = await response.json();
				if (Array.isArray(data)) {
					exportJobs = data.map((item: any) => ({
						id: item.id || String(Math.random()),
						name: item.name || '未知导出',
						type: item.type || 'training_corpus',
						format: item.format || 'jsonl',
						status: item.status || 'completed',
						progress: item.progress || 100,
						createdAt: new Date(item.created_at || Date.now()),
						fileSize: item.file_size || '未知',
						downloadUrl: item.download_url
					}));
				}
			}
		} catch (error) {
			console.error('获取导出历史失败:', error);
		}
	}
	
	const exportTypes = [
		{
			id: 'training_corpus',
			name: '训练语料',
			description: '用于大模型训练的结构化文本数据',
			icon: FileText,
			formats: [
				{ id: 'jsonl', name: 'JSONL', description: '每行一个JSON对象' },
				{ id: 'csv', name: 'CSV', description: '逗号分隔值文件' }
			]
		},
		{
			id: 'knowledge_graph',
			name: '知识图谱',
			description: '完整的图谱数据，包含节点和关系',
			icon: Database,
			formats: [
				{ id: 'neo4j', name: 'Neo4j Dump', description: '数据库备份文件' },
				{ id: 'json', name: 'JSON', description: '结构化JSON数据' }
			]
		}
	];
	
	function getCurrentFormats() {
		return exportTypes.find(t => t.id === selectedExportType)?.formats || [];
	}
	
	async function startExport() {
		if (!exportName.trim()) {
			alert('请输入导出任务名称');
			return;
		}
		
		try {
			isLoading = true;
			
			const response = await fetch('/api/v1/export/corpus', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					format_type: selectedFormat,
					group_id: null
				})
			});
			
			if (response.ok) {
				const result = await response.json();
				
				const newJob: ExportJob = {
					id: result.file_path || String(Math.random()),
					name: exportName,
					type: selectedExportType as any,
					format: selectedFormat,
					status: result.success ? 'completed' : 'failed',
					progress: 100,
					createdAt: new Date(),
					fileSize: result.file_size ? `${(result.file_size / 1024 / 1024).toFixed(2)} MB` : '未知',
					downloadUrl: result.file_path
				};
				
				exportJobs = [newJob, ...exportJobs];
				exportName = '';
				
				if (result.success) {
					alert(`导出成功！共 ${result.record_count} 条记录`);
				}
			} else {
				alert('导出失败，请重试');
			}
		} catch (error) {
			console.error('导出失败:', error);
			alert('导出失败，请重试');
		} finally {
			isLoading = false;
		}
	}
	
	async function downloadFile(job: ExportJob) {
		if (!job.downloadUrl) return;
		
		try {
			// 提取文件名
			const fileName = job.downloadUrl.split('/').pop() || `${job.name}.${job.format}`;
			
			const response = await fetch(`/api/v1/export/download/${fileName}`);
			if (response.ok) {
				const blob = await response.blob();
				const url = window.URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = fileName;
				document.body.appendChild(a);
				a.click();
				window.URL.revokeObjectURL(url);
				document.body.removeChild(a);
			} else {
				alert('下载失败，请重试');
			}
		} catch (error) {
			console.error('下载失败:', error);
			alert('下载失败，请重试');
		}
	}

	onMount(() => {
		fetchExportHistory();
	});
</script>

<svelte:head>
	<title>导出管理 - 桥梁知识图谱平台</title>
</svelte:head>

<div class="space-y-6">
	<div>
		<h1 class="text-3xl font-bold text-gray-900">导出管理</h1>
		<p class="mt-2 text-gray-600">导出知识图谱、训练语料和完整数据集</p>
	</div>

	<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
		<!-- Export Configuration -->
		<div class="lg:col-span-1">
			<div class="bg-white rounded-xl border border-gray-200 p-6">
				<h2 class="text-xl font-semibold text-gray-900 mb-6">创建导出任务</h2>
				
				<!-- Export Type Selection -->
				<div class="mb-6">
					<label class="block text-sm font-medium text-gray-700 mb-3">导出类型</label>
					<div class="space-y-3">
						{#each exportTypes as type}
							{@const TypeIcon = type.icon}
							<label class="flex items-start p-3 border rounded-lg cursor-pointer transition-colors duration-200
								{selectedExportType === type.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}"
								for="export-type-{type.id}">
								<input
									id="export-type-{type.id}"
									type="radio"
									bind:group={selectedExportType}
									value={type.id}
									class="mt-1 text-blue-600 focus:ring-blue-500"
								/>
								<div class="ml-3 flex-1">
									<div class="flex items-center">
										<TypeIcon class="w-4 h-4 mr-2 text-gray-600" />
										<span class="font-medium text-gray-900">{type.name}</span>
									</div>
									<p class="text-xs text-gray-600 mt-1">{type.description}</p>
								</div>
							</label>
						{/each}
					</div>
				</div>

				<!-- Format Selection -->
				<div class="mb-6">
					<label class="block text-sm font-medium text-gray-700 mb-3">导出格式</label>
					<select
						bind:value={selectedFormat}
						class="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					>
						{#each getCurrentFormats() as format}
							<option value={format.id}>{format.name} - {format.description}</option>
						{/each}
					</select>
				</div>

				<!-- Export Name -->
				<div class="mb-6">
					<label class="block text-sm font-medium text-gray-700 mb-2">任务名称</label>
					<input
						bind:value={exportName}
						type="text"
						placeholder="输入导出任务名称..."
						class="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					/>
				</div>

				<!-- Start Export Button -->
				<button
					onclick={startExport}
					disabled={!exportName.trim()}
					class="w-full flex items-center justify-center px-4 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors duration-200"
				>
					<Download class="w-5 h-5 mr-2" />
					开始导出
				</button>
			</div>
		</div>

		<!-- Export Jobs List -->
		<div class="lg:col-span-2">
			<div class="bg-white rounded-xl border border-gray-200">
				<div class="p-6 border-b border-gray-200">
					<h2 class="text-xl font-semibold text-gray-900">导出历史</h2>
				</div>

				{#if exportJobs.length === 0}
					<div class="p-8 text-center">
						<Download class="w-12 h-12 text-gray-300 mx-auto mb-4" />
						<h3 class="text-lg font-medium text-gray-900 mb-2">暂无导出任务</h3>
						<p class="text-gray-600">创建导出任务后将在此显示</p>
					</div>
				{:else}
					<div class="divide-y divide-gray-200">
						{#each exportJobs as job (job.id)}
							<div class="p-6">
								<div class="flex items-center justify-between">
									<div class="flex-1">
										<h3 class="text-sm font-medium text-gray-900">{job.name}</h3>
										<div class="mt-1 flex items-center space-x-4 text-xs text-gray-600">
											<span class="capitalize">{job.type.replace('_', ' ')}</span>
											<span>•</span>
											<span class="uppercase">{job.format}</span>
											{#if job.fileSize}
												<span>•</span>
												<span>{job.fileSize}</span>
											{/if}
										</div>
									</div>
									
									{#if job.status === 'completed' && job.downloadUrl}
										<button
											onclick={() => downloadFile(job)}
											class="flex items-center px-3 py-1 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-700 transition-colors duration-200"
										>
											<Download class="w-3 h-3 mr-1" />
											下载
										</button>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>
</div> 