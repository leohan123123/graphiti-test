<script lang="ts">
	import { Upload, FileText, File as FileIcon, CheckCircle, XCircle, AlertCircle, Trash2 } from 'lucide-svelte';
	import { websocketMessages, type FileStatusMessage } from '$lib/stores/websocketStore';
	import { onMount, onDestroy } from 'svelte';
	
	interface UploadFile {
		id: string; // This will be the server-assigned file_id after initial upload response
		clientSideId: string; // Temporary ID for display before server ID is known
		file: File;
		status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
		progress: number;
		error?: string;
		stage?: string; // For processing stage display
	}
	
	let files: UploadFile[] = $state([]);
	let dragOver = $state(false);
	let fileInput: HTMLInputElement;
	
	const allowedTypes = [
		'application/pdf',
		'application/msword',
		'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
		'image/vnd.dxf',
		'application/dxf'
	];
	
	const maxFileSize = 50 * 1024 * 1024; // 50MB
	
	function getFileIcon(file: File) {
		if (file.type === 'application/pdf') return FileText;
		if (file.type.includes('word')) return FileIcon;
		return FileIcon;
	}
	
	function formatFileSize(bytes: number): string {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const sizes = ['Bytes', 'KB', 'MB', 'GB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
	}
	
	function addFiles(newFiles: FileList | File[]) {
		const fileArray = Array.from(newFiles);
		
		for (const file of fileArray) {
			// 检查文件类型
			if (!allowedTypes.includes(file.type) && !file.name.toLowerCase().endsWith('.dxf')) {
				alert(`不支持的文件类型: ${file.name}`);
				continue;
			}
			
			// 检查文件大小
			if (file.size > maxFileSize) {
				alert(`文件过大: ${file.name} (最大支持 ${formatFileSize(maxFileSize)})`);
				continue;
			}
			
			// 检查是否已存在
			if (files.some(f => f.file.name === file.name && f.file.size === file.size)) {
				continue;
			}
			
			const clientSideId = Math.random().toString(36).substr(2, 9);
			const uploadFile: UploadFile = {
				id: '', // Server ID will be populated after successful upload
				clientSideId: clientSideId,
				file,
				status: 'pending',
				progress: 0
			};
			
			// Use spread to ensure reactivity when pushing to array
			files = [...files, uploadFile];
		}
	}
	
	function handleFileSelect(event: Event) {
		const target = event.target as HTMLInputElement;
		if (target.files) {
			addFiles(target.files);
		}
	}
	
	function handleDrop(event: DragEvent) {
		event.preventDefault();
		dragOver = false;
		
		if (event.dataTransfer?.files) {
			addFiles(event.dataTransfer.files);
		}
	}
	
	function handleDragOver(event: DragEvent) {
		event.preventDefault();
		dragOver = true;
	}
	
	function handleDragLeave(event: DragEvent) {
		event.preventDefault();
		dragOver = false;
	}
	
	function removeFile(clientSideIdToRemove: string) {
		files = files.filter(f => f.clientSideId !== clientSideIdToRemove);
	}
	
	function uploadFile(uploadFileToProcess: UploadFile) {
		return new Promise<void>((resolve, reject) => {
			const targetFile = files.find(f => f.clientSideId === uploadFileToProcess.clientSideId);
			if (!targetFile) {
				reject(new Error("File not found in list for upload."));
				return;
			}

			targetFile.status = 'uploading';
			targetFile.progress = 0;
			files = [...files]; // Trigger reactivity

			const formData = new FormData();
			formData.append('file', targetFile.file);

			const xhr = new XMLHttpRequest();
			xhr.open('POST', '/api/v1/documents/upload', true);

			xhr.upload.onprogress = (event) => {
				if (event.lengthComputable) {
					const percentComplete = Math.round((event.loaded / event.total) * 100);
					targetFile.progress = percentComplete;
					files = [...files];
				}
			};

			xhr.onload = async () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					const result = JSON.parse(xhr.responseText);
					targetFile.progress = 100;

					if (result.success && result.file_id) {
						targetFile.id = result.file_id; // Store the server-assigned file_id
						targetFile.status = 'processing';
						targetFile.progress = 0; // Reset progress for server-side processing phase
						targetFile.stage = '等待处理...';
						files = [...files];

						// Trigger backend processing
						try {
							const processResponse = await fetch(`/api/v1/documents/process/${result.file_id}?enable_ocr=true&build_graph=true`, {
								method: 'POST'
							});

							if (!processResponse.ok) {
								const errorText = await processResponse.text();
								throw new Error(`处理启动失败: ${processResponse.status} ${errorText}`);
							}
							// Processing started, WebSocket will handle updates from here.
							// No more polling needed.
							resolve();
						} catch (processError) {
							targetFile.status = 'error';
							targetFile.error = processError instanceof Error ? processError.message : '处理启动失败';
							files = [...files];
							reject(processError);
						}
					} else {
						targetFile.status = 'error';
						targetFile.error = result.message || '上传成功但服务器返回错误';
						files = [...files];
						reject(new Error(targetFile.error));
					}
				} else {
					targetFile.status = 'error';
					targetFile.error = `上传失败: ${xhr.status} ${xhr.statusText}`;
					files = [...files];
					reject(new Error(targetFile.error));
				}
			};

			xhr.onerror = () => {
				targetFile.status = 'error';
				targetFile.error = '网络错误或上传被中断';
				targetFile.progress = 0;
				files = [...files];
				reject(new Error(targetFile.error));
			};

			xhr.send(formData);
		});
	}
	
	// No longer need pollProcessingStatus due to WebSocket integration

	let unsubscribeFromWebsocket: (() => void) | null = null;

	onMount(() => {
		unsubscribeFromWebsocket = websocketMessages.subscribe(message => {
			if (message && message.type === 'file_status_update') {
				const data = message.payload as FileStatusMessage['payload'];
				const fileToUpdate = files.find(f => f.id === data.file_id);

				if (fileToUpdate) {
					fileToUpdate.status = data.status;
					fileToUpdate.progress = data.progress;
					fileToUpdate.stage = data.stage || fileToUpdate.stage;
					if (data.status === 'failed' && data.message) {
						fileToUpdate.error = data.message;
					}
					if (data.status === 'completed') {
						fileToUpdate.progress = 100;
					}
					files = [...files]; // Trigger Svelte reactivity
				}
			}
		});
	});

	onDestroy(() => {
		if (unsubscribeFromWebsocket) {
			unsubscribeFromWebsocket();
		}
	});
	
	async function uploadAll() {
		const pendingFiles = files.filter(f => f.status === 'pending');
		
		for (const file of pendingFiles) {
			await uploadFile(file);
		}
	}
	
	function clearCompleted() {
		files = files.filter(f => f.status !== 'completed');
	}
</script>

<svelte:head>
	<title>文档上传 - 桥梁知识图谱平台</title>
</svelte:head>

<div class="space-y-6">
	<!-- Page Header -->
	<div>
		<h1 class="text-3xl font-bold text-gray-900">文档上传</h1>
		<p class="mt-2 text-gray-600">
			上传PDF、Word、CAD等工程文档，系统将自动提取文本并构建知识图谱
		</p>
	</div>

	<!-- Upload Area -->
	<div class="bg-white rounded-xl border border-gray-200 p-8">
		<div 
			class="border-2 border-dashed rounded-lg p-8 text-center transition-colors duration-200
				   {dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}"
			role="button"
			tabindex="0"
			aria-label="拖拽文件到此处或点击选择文件"
			ondrop={handleDrop}
			ondragover={handleDragOver}
			ondragleave={handleDragLeave}
		>
			<Upload class="w-12 h-12 text-gray-400 mx-auto mb-4" />
			<h3 class="text-lg font-semibold text-gray-900 mb-2">
				拖拽文件到此处或点击选择
			</h3>
			<p class="text-gray-600 mb-4">
				支持 PDF, Word, DXF 格式，单个文件最大 50MB
			</p>
			<button
				onclick={() => fileInput.click()}
				class="inline-flex items-center px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors duration-200"
			>
				<Upload class="w-4 h-4 mr-2" />
				选择文件
			</button>
			<input
				bind:this={fileInput}
				type="file"
				multiple
				accept=".pdf,.doc,.docx,.dxf"
				onchange={handleFileSelect}
				class="hidden"
			/>
		</div>
	</div>

	<!-- File List -->
	{#if files.length > 0}
		<div class="bg-white rounded-xl border border-gray-200">
			<div class="p-6 border-b border-gray-200">
				<div class="flex items-center justify-between">
					<h2 class="text-xl font-semibold text-gray-900">
						上传列表 ({files.length})
					</h2>
					<div class="flex space-x-3">
						<button
							onclick={clearCompleted}
							class="text-sm text-gray-600 hover:text-gray-900 transition-colors duration-200"
						>
							清除已完成
						</button>
						<button
							onclick={uploadAll}
							disabled={!files.some(f => f.status === 'pending')}
							class="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors duration-200"
						>
							全部上传
						</button>
					</div>
				</div>
			</div>
			
			<div class="divide-y divide-gray-200">
				{#each files as file (file.clientSideId)} {{!-- Use clientSideId for key as server `id` might not be available initially --}}
					{@const FileIcon = getFileIcon(file.file)}
					<div class="p-6 flex items-center space-x-4">
						<!-- File Icon -->
						<div class="p-2 rounded-lg bg-gray-50">
							<FileIcon class="w-6 h-6 text-gray-600" />
						</div>
						
						<!-- File Info -->
						<div class="flex-1 min-w-0">
							<p class="text-sm font-medium text-gray-900 truncate">
								{file.file.name}
							</p>
							<p class="text-sm text-gray-500">
								{formatFileSize(file.file.size)}
							</p>
							
							<!-- Progress Bar -->
							{#if file.status === 'uploading' || file.status === 'processing'}
								<div class="mt-2 bg-gray-200 rounded-full h-2">
									<div 
										class="h-2 rounded-full transition-all duration-300
											{file.status === 'uploading' ? 'bg-blue-600' : 'bg-yellow-500'}"
										style="width: {file.progress}%"
									></div>
								</div>
								<p class="text-xs text-gray-500 mt-1">
									{#if file.status === 'uploading'}
										上传中... {file.progress}%
									{:else if file.status === 'processing'}
										{file.stage || '处理中'}... {file.progress}%
									{/if}
								</p>
							{/if}
						</div>
						
						<!-- Status -->
						<div class="flex items-center space-x-2 min-w-[120px] justify-end"> {{!-- Added min-width and justify-end --}}
							{#if file.status === 'pending'}
								<span class="text-sm text-gray-500">等待上传</span>
							{:else if file.status === 'uploading'}
								<span class="text-sm text-blue-600">上传中</span>
							{:else if file.status === 'processing'}
								<AlertCircle class="w-5 h-5 text-yellow-500" />
								<span class="text-sm text-yellow-600">{file.stage || '处理中'}</span>
							{:else if file.status === 'completed'}
								<CheckCircle class="w-5 h-5 text-green-500" />
								<span class="text-sm text-green-600">已完成</span>
							{:else if file.status === 'error'}
								<XCircle class="w-5 h-5 text-red-500" />
								<span class="text-sm text-red-600 truncate" title={file.error}>
									{file.error || '失败'}
								</span>
							{/if}
							
							<button
								onclick={() => removeFile(file.clientSideId)}
								class="p-1 text-gray-400 hover:text-red-500 transition-colors duration-200"
								title="移除文件"
							>
								<Trash2 class="w-4 h-4" />
							</button>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Tips -->
	<div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
		<h3 class="text-sm font-medium text-blue-900 mb-2">上传提示</h3>
		<ul class="text-sm text-blue-800 space-y-1">
			<li>• 支持的格式：PDF、Word (.doc/.docx)、AutoCAD (.dxf)</li>
			<li>• 建议文档内容清晰，避免扫描件模糊图像</li>
			<li>• 系统将自动识别桥梁工程专业术语和技术参数</li>
			<li>• 处理时间根据文档大小和复杂度而定，通常 1-5 分钟</li>
		</ul>
	</div>
</div> 