<script lang="ts">
	import { marked } from 'marked';
	import type { Message } from '../../../types';

	marked.setOptions({ breaks: true });

	let { message }: { message: Message } = $props();

	const isUser = $derived(message.role === 'user');
	const renderedContent = $derived(
		isUser ? message.content : (marked(message.content) as string)
	);

	let copied = $state(false);

	async function copy() {
		await navigator.clipboard.writeText(message.content);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}
</script>

<div class="flex {isUser ? 'justify-end' : 'justify-start'} mb-4">
	<div class="relative group max-w-[75%]">
		<div
			class="rounded-2xl px-4 py-2.5 text-sm {isUser
				? 'bg-primary text-primary-foreground'
				: 'bg-muted text-foreground'}"
		>
			{#if isUser}
				<p class="whitespace-pre-wrap">{message.content}</p>
			{:else}
				<!-- eslint-disable-next-line svelte/no-at-html-tags -->
				<div class="prose prose-sm dark:prose-invert max-w-none">
					{@html renderedContent}{#if message.streaming}<span class="animate-pulse">▋</span>{/if}
				</div>
			{/if}
		</div>

		{#if !isUser && !message.streaming}
			<button
				onclick={copy}
				title="Copy"
				class="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity
				       p-1 rounded text-muted-foreground hover:text-foreground hover:bg-background/80"
			>
				{#if copied}
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
				{/if}
			</button>
		{/if}
	</div>
</div>
