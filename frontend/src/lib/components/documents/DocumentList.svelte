<script lang="ts">
	import type { Document } from '../../../types';

	let { documents, ondelete, currentUserId }: { documents: Document[]; ondelete: (id: string) => void; currentUserId: string } = $props();

	let expandedId = $state<string | null>(null);

	function toggle(id: string) {
		expandedId = expandedId === id ? null : id;
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function formatDate(iso: string): string {
		return new Date(iso).toLocaleDateString(undefined, {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit',
		});
	}

	const statusConfig: Record<string, { label: string; classes: string }> = {
		pending: {
			label: 'Pending',
			classes: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
		},
		parsing: {
			label: 'Parsing',
			classes: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
		},
		processing: {
			label: 'Processing',
			classes: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
		},
		completed: {
			label: 'Indexed',
			classes: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
		},
		failed: {
			label: 'Failed',
			classes: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
		},
	};
</script>

{#if documents.length === 0}
	<p class="text-muted-foreground py-8 text-center text-sm">No documents uploaded yet</p>
{:else}
	<div class="space-y-2">
		{#each documents as doc (doc.id)}
			{@const status = statusConfig[doc.status] ?? statusConfig.pending}
			{@const expanded = expandedId === doc.id}
			<div class="bg-card rounded-lg border">
				<!-- Header row -->
				<div class="flex items-center gap-2 p-3">
					<!-- Chevron toggle (only when metadata available) -->
					{#if doc.metadata}
						<button
							type="button"
							onclick={() => toggle(doc.id)}
							class="text-muted-foreground shrink-0 rounded p-0.5 transition-transform {expanded ? 'rotate-90' : ''}"
							aria-label="Toggle details"
						>
							<svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7" />
							</svg>
						</button>
					{:else}
						<span class="w-5 shrink-0"></span>
					{/if}

					<div class="flex min-w-0 flex-1 flex-col gap-0.5">
						<div class="flex items-center gap-2">
							<span class="truncate text-sm font-medium">{doc.filename}</span>
							<span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium {status.classes}">
								{status.label}
							</span>
						</div>
						<div class="text-muted-foreground flex gap-3 text-xs">
							<span>{formatSize(doc.file_size)}</span>
							{#if doc.status === 'parsing'}
								<span>Reading document…</span>
							{:else if doc.status === 'processing' && doc.chunks_total}
								<span>Embedding {doc.chunks_processed ?? 0} / {doc.chunks_total} chunks</span>
							{:else if doc.chunk_count}
								<span>{doc.chunk_count} chunks</span>
							{/if}
							<span>{formatDate(doc.created_at)}</span>
						</div>
						{#if doc.error_message}
							<p class="mt-0.5 text-xs text-red-500">{doc.error_message}</p>
						{/if}
					</div>

					{#if doc.user_id === currentUserId}
						<button
							type="button"
							onclick={() => ondelete(doc.id)}
							class="text-muted-foreground hover:text-destructive ml-1 shrink-0 rounded p-1 transition-colors"
							aria-label="Delete {doc.filename}"
						>
							<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
							</svg>
						</button>
					{/if}
				</div>

				<!-- Expandable metadata panel -->
				{#if doc.metadata && expanded}
					<div class="border-t px-4 pb-4 pt-3">
						<dl class="space-y-3 text-xs">
							<div class="flex gap-3">
								<dt class="text-muted-foreground/60 w-20 shrink-0">Summary</dt>
								<dd class="text-muted-foreground leading-relaxed">{doc.metadata.summary}</dd>
							</div>
							<div class="flex gap-3">
								<dt class="text-muted-foreground/60 w-20 shrink-0">Doc type</dt>
								<dd>
									<span class="rounded-full bg-muted/50 px-2 py-0.5 text-muted-foreground/70">
										{doc.metadata.doc_type}
									</span>
								</dd>
							</div>
							<div class="flex gap-3">
								<dt class="text-muted-foreground/60 w-20 shrink-0">Language</dt>
								<dd class="text-muted-foreground uppercase">{doc.metadata.language}</dd>
							</div>
							{#if doc.metadata.topics.length > 0}
								<div class="flex gap-3">
									<dt class="text-muted-foreground/60 w-20 shrink-0">Tags</dt>
									<dd class="flex flex-wrap gap-1">
										{#each doc.metadata.topics as topic}
											<span class="rounded-full bg-muted/40 px-2 py-0.5 text-muted-foreground/70">{topic}</span>
										{/each}
									</dd>
								</div>
							{/if}
						</dl>
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}
