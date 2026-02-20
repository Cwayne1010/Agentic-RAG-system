<script lang="ts">
	import { marked } from 'marked';
	import type { Message } from '../../../types';

	let { message }: { message: Message } = $props();

	const isUser = $derived(message.role === 'user');
	const renderedContent = $derived(
		isUser ? message.content : (marked(message.content) as string)
	);
</script>

<div class="flex {isUser ? 'justify-end' : 'justify-start'} mb-4">
	<div
		class="max-w-[75%] rounded-2xl px-4 py-2.5 text-sm {isUser
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
</div>
