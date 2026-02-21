<script lang="ts">
	import type { Document } from '../../../types';

	let { documents, ondelete }: { documents: Document[]; ondelete: (id: string) => void } = $props();

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
			<div class="bg-card flex items-center justify-between rounded-lg border p-3">
				<div class="flex min-w-0 flex-1 flex-col gap-0.5">
					<div class="flex items-center gap-2">
						<span class="truncate text-sm font-medium">{doc.filename}</span>
						<span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium {status.classes}">
							{status.label}
						</span>
					</div>
					<div class="text-muted-foreground flex gap-3 text-xs">
						<span>{formatSize(doc.file_size)}</span>
						{#if doc.chunk_count}
							<span>{doc.chunk_count} chunks</span>
						{/if}
						<span>{formatDate(doc.created_at)}</span>
					</div>
					{#if doc.error_message}
						<p class="mt-0.5 text-xs text-red-500">{doc.error_message}</p>
					{/if}
				</div>
				<button
					type="button"
					onclick={() => ondelete(doc.id)}
					class="text-muted-foreground hover:text-destructive ml-3 shrink-0 rounded p-1 transition-colors"
					aria-label="Delete {doc.filename}"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="h-4 w-4"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
						/>
					</svg>
				</button>
			</div>
		{/each}
	</div>
{/if}
