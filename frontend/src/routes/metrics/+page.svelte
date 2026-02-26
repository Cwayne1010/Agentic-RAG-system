<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { apiRequest } from '$lib/api';

	interface Job {
		id: string;
		filename: string;
		status: string;
		chunks_total: number | null;
		chunks_processed: number | null;
		created_at: string;
	}

	interface Metrics {
		memory_rss_mb: number;
		memory_vms_mb: number;
		cpu_percent: number;
		active_jobs: Job[];
	}

	let metrics: Metrics | null = $state(null);
	let error: string | null = $state(null);
	let lastUpdated: Date | null = $state(null);
	let interval: ReturnType<typeof setInterval>;

	async function fetchMetrics() {
		try {
			metrics = await apiRequest<Metrics>('/api/metrics');
			lastUpdated = new Date();
			error = null;
		} catch (e) {
			error = String(e);
		}
	}

	onMount(() => {
		fetchMetrics();
		interval = setInterval(fetchMetrics, 1000);
	});

	onDestroy(() => clearInterval(interval));

	function cpuColor(pct: number) {
		if (pct > 80) return 'text-red-400';
		if (pct > 50) return 'text-yellow-400';
		return 'text-green-400';
	}

	function progressPct(job: Job) {
		if (!job.chunks_total || job.chunks_processed == null) return 0;
		return Math.min(100, Math.round((job.chunks_processed / job.chunks_total) * 100));
	}

	function memBarColor(mb: number) {
		if (mb > 1500) return 'bg-red-500';
		if (mb > 800) return 'bg-yellow-500';
		return 'bg-blue-500';
	}
</script>

<svelte:head>
	<title>RAG Monitor</title>
</svelte:head>

<div class="min-h-screen bg-gray-950 text-gray-100 p-4 font-mono text-sm select-none">
	<!-- Header -->
	<div class="flex items-center justify-between mb-5">
		<h1 class="text-sm font-bold tracking-widest text-gray-300 uppercase">RAG Monitor</h1>
		{#if lastUpdated}
			<span class="text-gray-600 text-xs">{lastUpdated.toLocaleTimeString()}</span>
		{/if}
	</div>

	{#if error}
		<div class="text-red-400 text-xs bg-red-950 border border-red-800 rounded p-2 mb-4">{error}</div>
	{/if}

	{#if metrics}
		<!-- Memory -->
		<div class="mb-5">
			<div class="text-gray-500 text-xs uppercase tracking-widest mb-2">Memory (RSS)</div>
			<div class="flex items-end gap-2 mb-1">
				<span class="text-3xl font-bold text-white">{metrics.memory_rss_mb}</span>
				<span class="text-gray-500 text-sm mb-1">MB</span>
				<span class="text-gray-600 text-xs mb-1 ml-auto">VMS {metrics.memory_vms_mb} MB</span>
			</div>
			<div class="h-1 bg-gray-800 rounded-full overflow-hidden">
				<div
					class="h-full rounded-full transition-all duration-500 {memBarColor(metrics.memory_rss_mb)}"
					style="width: {Math.min(100, (metrics.memory_rss_mb / 2048) * 100)}%"
				></div>
			</div>
			<div class="text-gray-700 text-xs mt-0.5 text-right">/ 2048 MB</div>
		</div>

		<!-- CPU -->
		<div class="mb-5">
			<div class="text-gray-500 text-xs uppercase tracking-widest mb-2">CPU</div>
			<div class="flex items-end gap-2 mb-1">
				<span class="text-3xl font-bold {cpuColor(metrics.cpu_percent)}">{metrics.cpu_percent}</span>
				<span class="text-gray-500 text-sm mb-1">%</span>
			</div>
			<div class="h-1 bg-gray-800 rounded-full overflow-hidden">
				<div
					class="h-full rounded-full transition-all duration-300 {cpuColor(metrics.cpu_percent).replace('text-', 'bg-')}"
					style="width: {metrics.cpu_percent}%"
				></div>
			</div>
		</div>

		<div class="border-t border-gray-800 my-4"></div>

		<!-- Active Jobs -->
		<div>
			<div class="text-gray-500 text-xs uppercase tracking-widest mb-3">
				Uploads
				<span class="ml-1 text-gray-600">({metrics.active_jobs.length} active)</span>
			</div>

			{#if metrics.active_jobs.length === 0}
				<div class="text-gray-700 text-xs py-4 text-center">No active uploads</div>
			{:else}
				{#each metrics.active_jobs as job (job.id)}
					<div class="mb-3 bg-gray-900 rounded-lg p-3 border border-gray-800">
						<div class="flex items-center justify-between mb-2">
							<span class="text-gray-200 text-xs truncate max-w-[75%]" title={job.filename}>
								{job.filename}
							</span>
							<span class="text-xs px-1.5 py-0.5 rounded {job.status === 'processing' ? 'bg-blue-900 text-blue-300' : 'bg-gray-800 text-gray-400'}">
								{job.status}
							</span>
						</div>

						{#if job.chunks_total}
							<div class="flex items-center gap-2">
								<div class="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
									<div
										class="h-full bg-blue-500 rounded-full transition-all duration-500"
										style="width: {progressPct(job)}%"
									></div>
								</div>
								<span class="text-xs text-gray-500 whitespace-nowrap tabular-nums">
									{job.chunks_processed ?? 0}/{job.chunks_total}
								</span>
								<span class="text-xs text-gray-600 w-8 text-right tabular-nums">
									{progressPct(job)}%
								</span>
							</div>
						{:else}
							<div class="flex items-center gap-2">
								<div class="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
									<div class="h-full bg-gray-700 rounded-full animate-pulse w-1/3"></div>
								</div>
								<span class="text-xs text-gray-600">parsing…</span>
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	{:else if !error}
		<div class="text-gray-600 text-xs animate-pulse">Connecting…</div>
	{/if}
</div>
