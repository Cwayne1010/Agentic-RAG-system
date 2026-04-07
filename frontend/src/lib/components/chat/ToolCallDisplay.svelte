<script lang="ts">
	import { slide } from 'svelte/transition';

	type WebResult = { title: string; url: string };
	type DocSource = { name: string; chunks: number };

	type TC = {
		tool_name: string;
		args: object;
		status: 'running' | 'done';
		result?: object;
		children?: TC[];
	};

	type Props = { tc: TC; stateKey?: string };
	let { tc, stateKey = '' }: Props = $props();

	const _storageKey = $derived(stateKey ? `tcd:${stateKey}` : '');
	function initialOpen(): boolean {
		return stateKey ? localStorage.getItem(`tcd:${stateKey}`) === '1' : false;
	}
	let open = $state(initialOpen());

	function toggle() {
		open = !open;
		if (_storageKey) localStorage.setItem(_storageKey, open ? '1' : '0');
	}

	const args   = $derived(tc.args   as Record<string, unknown>);
	const result = $derived(tc.result as Record<string, unknown> | undefined);

	const query = $derived((args.query ?? args.question ?? '') as string);
	const task  = $derived((args.task  ?? '') as string);
	const subject = $derived(query || task);

	const webResults = $derived((result?.results as WebResult[] | undefined) ?? []);
	const docSources = $derived((result?.sources  as DocSource[] | undefined) ?? []);
	const sql        = $derived(result?.sql as string | undefined);

	const chunkCount  = $derived(result?.chunk_count  as number | undefined);
	const rowCount    = $derived(result?.row_count    as number | undefined);
	const resultCount = $derived(result?.result_count as number | undefined);

	// Total chunks across all sub-agent retrieve_documents calls
	const subAgentChunkTotal = $derived(
		tc.children
			?.filter(c => c.tool_name === 'retrieve_documents')
			.reduce((sum, c) => sum + ((c.result as { chunk_count?: number })?.chunk_count ?? 0), 0) ?? 0
	);

	// Compact sources summary: "Budget.pdf, Report.pdf +2"
	const sourcesSummary = $derived(() => {
		if (docSources.length === 0) return '';
		const shown = docSources.slice(0, 2).map(s => s.name).join(', ');
		return docSources.length > 2 ? `${shown} +${docSources.length - 2}` : shown;
	});

	// Rich inline header — changes as data arrives
	const headerLine = $derived(() => {
		const running = tc.status === 'running';

		if (tc.tool_name === 'retrieve_documents') {
			if (running) return subject ? `Searching docs for "${subject}"` : 'Searching docs…';
			const parts = ['Searched docs'];
			if (chunkCount !== undefined) parts.push(`${chunkCount} chunk${chunkCount !== 1 ? 's' : ''}`);
			if (sourcesSummary()) parts.push(sourcesSummary());
			return parts.join(' · ');
		}

		if (tc.tool_name === 'web_search') {
			if (running) return subject ? `Searching the web for "${subject}"` : 'Searching the web…';
			const parts = ['Searched the web'];
			if (resultCount !== undefined) parts.push(`${resultCount} result${resultCount !== 1 ? 's' : ''}`);
			else if (webResults.length > 0) parts.push(`${webResults.length} result${webResults.length !== 1 ? 's' : ''}`);
			return parts.join(' · ');
		}

		if (tc.tool_name === 'query_database') {
			if (running) return subject ? `Querying database: ${subject}` : 'Querying database…';
			const parts = ['Queried database'];
			if (rowCount !== undefined) parts.push(`${rowCount} row${rowCount !== 1 ? 's' : ''}`);
			if (sql) parts.push('SQL ▾');
			return parts.join(' · ');
		}

		if (tc.tool_name === 'spawn_document_agent') {
			if (running) {
				const childCount = tc.children?.length ?? 0;
				if (childCount > 0) {
					const doneCount = tc.children?.filter(c => c.status === 'done').length ?? 0;
					return `Document agent · ${doneCount}/${childCount} tools done`;
				}
				return subject ? `Document agent: ${subject}` : 'Running document agent…';
			}
			const parts = ['Document agent'];
			if (tc.children && tc.children.length > 0) {
				parts.push(`${tc.children.length} tool${tc.children.length !== 1 ? 's' : ''} used`);
			}
			if (subAgentChunkTotal > 0) {
				parts.push(`${subAgentChunkTotal} chunk${subAgentChunkTotal !== 1 ? 's' : ''}`);
			}
			return parts.join(' · ');
		}

		return running ? tc.tool_name : tc.tool_name;
	});

	function domainOf(url: string): string {
		try { return new URL(url).hostname.replace(/^www\./, ''); }
		catch { return url; }
	}

	function initial(s: string): string {
		return (s[0] ?? '?').toUpperCase();
	}
</script>

<div class="w-full text-sm">

	<!-- ── Header row ─────────────────────────────────── -->
	<button
		onclick={toggle}
		class="flex w-full items-center gap-2 py-0.5 pr-2 text-left text-muted-foreground hover:text-foreground transition-colors"
	>
		{#if tc.status === 'running'}
			<span class="animate-spin text-xs leading-none shrink-0">⟳</span>
		{:else}
			<svg class="h-3.5 w-3.5 shrink-0 text-green-500" viewBox="0 0 24 24" fill="none"
				stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
				<circle cx="12" cy="12" r="10"/>
				<polyline points="9 12 11 14 15 10"/>
			</svg>
		{/if}

		<span class="flex items-center gap-0.5 min-w-0 text-xs">
			<span class="truncate">{headerLine()}</span>
			<svg
				class="h-3 w-3 shrink-0 transition-transform duration-150 {open ? 'rotate-180' : ''}"
				viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
				stroke-linecap="round" stroke-linejoin="round"
			>
				<polyline points="6 9 12 15 18 9"/>
			</svg>
		</span>
	</button>

	<!-- ── Expandable detail (no card box) ───────────── -->
	{#if open}
		<div transition:slide={{ duration: 150, axis: 'y' }} class="mt-1 pl-5 pr-2 text-xs text-muted-foreground space-y-1">

			<!-- Query / task (if not already obvious from header) -->
			{#if subject && (tc.tool_name === 'query_database' || tc.tool_name === 'spawn_document_agent')}
				<p class="italic opacity-70">{subject}</p>
			{/if}

			<!-- Web results -->
			{#if webResults.length > 0}
				<ul class="space-y-0.5">
					{#each webResults as r}
						{@const domain = domainOf(r.url)}
						<li>
							<a href={r.url} target="_blank" rel="noopener noreferrer" class="flex items-center gap-2 cursor-pointer hover:text-foreground transition-colors">
								<span class="flex-1 truncate">{r.title}</span>
								<span class="shrink-0 opacity-50">{domain}</span>
							</a>
						</li>
					{/each}
				</ul>
			{/if}

			<!-- Doc sources -->
			{#if docSources.length > 0}
				<ul class="space-y-0.5">
					{#each docSources as src}
						<li class="truncate">
							{src.name}<span class="opacity-50"> · {src.chunks} chunk{src.chunks !== 1 ? 's' : ''}</span>
						</li>
					{/each}
				</ul>
			{/if}

			<!-- SQL snippet -->
			{#if sql}
				<code class="block break-all font-mono text-[10px] opacity-70">{sql}</code>
			{/if}

			<!-- Sub-agent children -->
			{#if tc.children && tc.children.length > 0}
				<ul class="space-y-0.5">
					{#each tc.children as child, i (child.tool_name + i)}
						<li class="flex items-center gap-2">
							{#if child.status === 'running'}
								<span class="animate-spin text-xs leading-none">⟳</span>
							{:else}
								<svg class="h-3 w-3 shrink-0 text-green-500" viewBox="0 0 24 24" fill="none"
									stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
									<circle cx="12" cy="12" r="10"/>
									<polyline points="9 12 11 14 15 10"/>
								</svg>
							{/if}
							<span>
								{child.tool_name === 'retrieve_documents' ? 'Searching docs' : child.tool_name}
								{#if (child.result as {chunk_count?: number})?.chunk_count !== undefined}
									· {(child.result as {chunk_count: number}).chunk_count} chunks
								{/if}
							</span>
						</li>
					{/each}
				</ul>
			{/if}

			<!-- Empty running state -->
			{#if !subject && tc.status === 'running' && !tc.children?.length}
				<div class="flex items-center gap-2">
					<span class="animate-spin">⟳</span>
					<span>Working…</span>
				</div>
			{/if}
		</div>
	{/if}
</div>
