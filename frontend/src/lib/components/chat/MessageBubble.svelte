<script lang="ts">
	import { fade } from 'svelte/transition';
	import { marked } from 'marked';
	import type { Message } from '../../../types';
	import ToolCallDisplay from './ToolCallDisplay.svelte';

	type ToolCall = {
		tool_name: string;
		args: object;
		status: 'running' | 'done';
		result?: object;
		children?: ToolCall[];
	};

	marked.setOptions({ breaks: true });

	let { message, toolCalls = [] }: { message: Message; toolCalls?: ToolCall[] } = $props();

	const isUser = $derived(message.role === 'user');

	// Tool calls: live during streaming, persisted after done
	const visibleToolCalls = $derived(
		message.streaming ? toolCalls : (message.toolCalls ?? [])
	);

	// Split content at tool call boundary
	const offset = $derived(message.toolCallOffset);
	const preContent = $derived(
		offset !== undefined ? (marked(message.content.slice(0, offset)) as string) : null
	);
	const postContent = $derived(
		offset !== undefined && message.content.length > offset
			? (marked(message.content.slice(offset)) as string)
			: null
	);
	const fullContent = $derived(marked(message.content) as string);

	const hasTools = $derived(visibleToolCalls.length > 0 || preContent !== null);

	// The copy button lives in the last/only bubble — needs extra bottom padding
	const bubblePadding = 'px-4 pt-2.5 pb-8 text-sm bg-muted text-foreground';

	let copied = $state(false);

	async function copy() {
		await navigator.clipboard.writeText(message.content);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}
</script>

{#if isUser}
	<div class="flex justify-end mb-4">
		<div class="max-w-[75%] rounded-2xl px-4 py-2.5 text-sm bg-primary text-primary-foreground">
			<p class="whitespace-pre-wrap">{message.content}</p>
		</div>
	</div>
{:else if hasTools}
	<div class="mb-4">
		<!-- Pre-text bubble -->
		{#if preContent}
			<div class="w-full rounded-2xl px-4 py-2.5 text-sm bg-muted text-foreground mb-1">
				<!-- eslint-disable-next-line svelte/no-at-html-tags -->
				<div class="prose prose-sm dark:prose-invert max-w-none">{@html preContent}</div>
			</div>
		{/if}

		<!-- Tool call row -->
		{#if visibleToolCalls.length > 0}
			<div class="flex flex-col gap-1 py-0.5 pr-3" transition:fade={{ duration: 150 }}>
				{#each visibleToolCalls as tc, i (tc.tool_name)}
					<ToolCallDisplay {tc} stateKey="{message.id}-{i}" />
				{/each}
			</div>
		{/if}

		<!-- Post-text bubble — copy icon lives here -->
		{#if postContent || (message.streaming && preContent !== null)}
			<div class="relative group w-full rounded-2xl {bubblePadding} mt-1">
				<!-- eslint-disable-next-line svelte/no-at-html-tags -->
				<div class="prose prose-sm dark:prose-invert max-w-none">
					{#if postContent}{@html postContent}{/if}{#if message.streaming}<span class="animate-pulse">▋</span>{/if}
				</div>
				{#if !message.streaming}
					<button
						onclick={copy}
						title="Copy"
						class="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity
						       p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-background/60"
					>
						{#if copied}
							<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
						{:else}
							<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
						{/if}
					</button>
				{/if}
			</div>
		{/if}
	</div>
{:else}
	<!-- Standard single bubble — copy icon lives here -->
	<div class="relative group w-full rounded-2xl {bubblePadding} mb-4">
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		<div class="prose prose-sm dark:prose-invert max-w-none">
			{@html fullContent}{#if message.streaming}<span class="animate-pulse">▋</span>{/if}
		</div>
		{#if !message.streaming}
			<button
				onclick={copy}
				title="Copy"
				class="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity
				       p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-background/60"
			>
				{#if copied}
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
				{/if}
			</button>
		{/if}
	</div>
{/if}
