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
	
	let selectedExportType = $state<'training_corpus' | 'knowledge_graph'>('training_corpus');
	let selectedFormat = $state('jsonl');
	let exportName = $state('');
	
	let exportJobs: ExportJob[] = $state([]);
	let isLoading = $state(false);
	let globalError = $state<string | null>(null);
	let globalSuccess = $state<string | null>(null);

	// 获取导出历史
	async function fetchExportHistory() {
		isLoading = true;
		globalError = null;
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
			} else {
				globalError = `获取导出历史失败: ${response.status} ${response.statusText}`;
				console.error(globalError);
			}
		} catch (error) {
			globalError = error instanceof Error ? error.message : '获取导出历史发生未知错误';
			console.error('获取导出历史失败:', error);
		} finally {
			isLoading = false;
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

	$effect(() => {
		// When selectedExportType changes, reset selectedFormat to the first available format of the new type
		const currentAvailableFormats = getCurrentFormats();
		if (currentAvailableFormats.length > 0) {
			if (!currentAvailableFormats.some(f => f.id === selectedFormat)) {
				selectedFormat = currentAvailableFormats[0].id;
			}
		} else {
			selectedFormat = ''; // Or some default/empty state
		}
	});
	
	async function startExport() {
		globalError = null;
		globalSuccess = null;
		if (!exportName.trim()) {
			globalError = '请输入导出任务名称';
			return;
		}
		
		isLoading = true;
		let exportEndpoint = '';
		let payload: any = {};

		if (selectedExportType === 'training_corpus') {
			exportEndpoint = '/api/v1/export/corpus';
			payload = {
				format_type: selectedFormat,
				// group_id: null // Assuming group_id is not used for now or handled differently
			};
		} else if (selectedExportType === 'knowledge_graph') {
			exportEndpoint = '/api/v1/export/graph'; // Example endpoint for graph
			payload = {
				format_type: selectedFormat, // e.g., 'json', 'neo4j_dump'
				// Add other graph-specific params if needed, e.g. graph_id: 'full'
			};
		} else {
			globalError = '未知的导出类型';
			isLoading = false;
			return;
		}

		try {
			const response = await fetch(exportEndpoint, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			
			const result = await response.json();

			if (response.ok && result.success) {
				const newJob: ExportJob = {
					id: result.job_id || result.file_path || String(Math.random()), // Prefer job_id if available
					name: exportName,
					type: selectedExportType,
					format: selectedFormat,
					status: result.status || 'completed', // Backend might return a status
					progress: result.progress || 100,
					createdAt: new Date(),
					fileSize: result.file_size ? `${(result.file_size / 1024 / 1024).toFixed(2)} MB` : undefined,
					downloadUrl: result.file_path // This might be populated later if async
				};
				
				exportJobs = [newJob, ...exportJobs.filter(job => job.id !== newJob.id)];
				exportName = ''; // Clear input field
				globalSuccess = `导出任务 "${newJob.name}" 已成功启动/完成。`;
				if (result.record_count) {
					globalSuccess += ` 共 ${result.record_count} 条记录。`;
				}
				// If the job is immediately completed and a download URL is available,
				// you might want to trigger download or inform user.
				// For now, user can click download from the list.

			} else {
				globalError = result.message || `导出失败: ${response.status}`;
				// Add a failed job to the list for visibility
				const failedJob: ExportJob = {
					id: String(Math.random()), name: exportName, type: selectedExportType, format: selectedFormat,
					status: 'failed', progress: 0, createdAt: new Date(),
					downloadUrl: undefined, fileSize: undefined
				};
				exportJobs = [failedJob, ...exportJobs.filter(job => job.name !== failedJob.name)];
			}
		} catch (error) {
			console.error('导出请求失败:', error);
			globalError = error instanceof Error ? error.message : '导出过程中发生未知网络错误。';
		} finally {
			isLoading = false;
		}
	}
	
	async function downloadFile(job: ExportJob) {
		if (!job.downloadUrl) {
			globalError = "此任务没有可用的下载链接。";
			return;
		}
		globalError = null;
		globalSuccess = null;
		
		// Use the full downloadUrl if it's an absolute path, or construct if relative
		const downloadPath = job.downloadUrl.startsWith('/')
			? job.downloadUrl
			: `/api/v1/export/download/${job.downloadUrl}`; // Assuming relative path is just filename

		try {
			// Forcing a unique query param can help bypass browser cache for the download link if needed
			const response = await fetch(`${downloadPath}?t=${new Date().getTime()}`);
			
			if (response.ok) {
				const blob = await response.blob();
				const guessedFileName = job.downloadUrl.split('/').pop() || `${job.name}.${job.format}`;

				// Try to get filename from Content-Disposition header
				const disposition = response.headers.get('content-disposition');
				let fileName = guessedFileName;
				if (disposition && disposition.includes('attachment')) {
					const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
					const matches = filenameRegex.exec(disposition);
					if (matches?.[1]) {
						fileName = matches[1].replace(/['"]/g, '');
					}
				}

				const url = window.URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = fileName;
				document.body.appendChild(a);
				a.click();
				a.remove(); // Clean up the element
				window.URL.revokeObjectURL(url);
				globalSuccess = `文件 "${fileName}" 已开始下载。`;
			} else {
				const errorText = await response.text();
				globalError = `下载失败: ${response.status}. ${errorText || ''}`;
			}
		} catch (error) {
			console.error('下载请求失败:', error);
			globalError = error instanceof Error ? error.message : '下载过程中发生未知网络错误。';
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

	<!-- Global Messages -->
	{#if globalError}
		<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
			<strong class="font-bold">错误!</strong>
			<span class="block sm:inline"> {globalError}</span>
			<button class="absolute top-0 bottom-0 right-0 px-4 py-3" onclick={() => globalError = null}>
				<XCircle class="w-5 h-5 text-red-500" />
			</button>
		</div>
	{/if}
	{#if globalSuccess}
		<div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative mb-4" role="alert">
			<strong class="font-bold">成功!</strong>
			<span class="block sm:inline"> {globalSuccess}</span>
			<button class="absolute top-0 bottom-0 right-0 px-4 py-3" onclick={() => globalSuccess = null}>
				<XCircle class="w-5 h-5 text-green-500" />
			</button>
		</div>
	{/if}

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
				<div class="p-6 border-b border-gray-200 flex justify-between items-center">
					<h2 class="text-xl font-semibold text-gray-900">导出历史</h2>
					<button
						onclick={fetchExportHistory}
						disabled={isLoading}
						class="p-2 text-gray-500 hover:text-blue-600 disabled:text-gray-300 transition-colors"
						title="刷新导出历史"
					>
						<RefreshCw class="w-5 h-5 {isLoading ? 'animate-spin' : ''}" />
					</button>
				</div>

				{#if isLoading && exportJobs.length === 0}
					<div class="p-8 text-center text-gray-500">正在加载历史记录...</div>
				{:else if exportJobs.length === 0}
					<div class="p-8 text-center">
						<Package class="w-12 h-12 text-gray-300 mx-auto mb-4" />
						<h3 class="text-lg font-medium text-gray-900 mb-2">暂无导出任务</h3>
						<p class="text-gray-600">创建导出任务后将在此显示</p>
					</div>
				{:else}
					<div class="divide-y divide-gray-200">
						{#each exportJobs as job (job.id)}
							<div class="p-6">
								<div class="flex items-center justify-between">
									<div class="flex-1 min-w-0"> {{!-- Added min-w-0 for truncation --}}
										<h3 class="text-sm font-medium text-gray-900 truncate" title={job.name}>{job.name}</h3>
										<div class="mt-1 flex items-center flex-wrap gap-x-3 gap-y-1 text-xs text-gray-600">
											<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize
												{job.status === 'completed' ? 'bg-green-100 text-green-800' :
												 job.status === 'failed' ? 'bg-red-100 text-red-800' :
												 'bg-yellow-100 text-yellow-800'}">
												{job.status === 'pending' ? '待处理' : job.status === 'processing' ? '处理中' : job.status === 'completed' ? '已完成' : '失败'}
											</span>
											<span class="capitalize">{job.type.replace('_', ' ')}</span>
											<span class="uppercase">{job.format}</span>
											{#if job.fileSize}
												<span>{job.fileSize}</span>
											{/if}
											<span class="text-gray-400" title={new Date(job.createdAt).toLocaleString()}>
												{new Date(job.createdAt).toLocaleDateString()}
											</span>
										</div>
									</div>
									
									<div class="ml-4 flex-shrink-0">
										{#if job.status === 'completed' && job.downloadUrl}
											<button
												onclick={() => downloadFile(job)}
												class="flex items-center px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-md hover:bg-blue-700 transition-colors duration-200"
												title="下载文件"
											>
												<Download class="w-4 h-4 mr-1.5" />
												下载
											</button>
										{:else if job.status === 'failed'}
											<span class="flex items-center text-red-500 text-xs" title={job.error || '导出失败'}>
												<AlertCircle class="w-4 h-4 mr-1" />
												失败
											</span>
										{:else if job.status === 'processing'}
											<span class="flex items-center text-yellow-600 text-xs">
												<RefreshCw class="w-4 h-4 mr-1 animate-spin" />
												处理中...
											</span>
										{/if}
									</div>
								</div>
								{#if job.status === 'processing' && job.progress > 0 && job.progress < 100}
								<div class="mt-2 bg-gray-200 rounded-full h-1.5">
									<div class="bg-yellow-500 h-1.5 rounded-full" style="width: {job.progress}%"></div>
								</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	</div>
</div> 