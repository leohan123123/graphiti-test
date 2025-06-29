<script lang="ts">
	import '../app.css';
	import Navbar from '$lib/components/Navbar.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	
	let { children } = $props();
	let sidebarCollapsed = $state(false);
</script>

<div class="min-h-screen bg-gray-50/50">
	<!-- 顶部导航栏 -->
	<Navbar />
	
	<!-- 侧边栏 -->
	<Sidebar bind:collapsed={sidebarCollapsed} />
	
	<!-- 主内容区域 -->
	<main class="transition-all duration-300 {sidebarCollapsed ? 'ml-16' : 'ml-64'} pt-4">
		<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
			{@render children()}
		</div>
	</main>
</div>
