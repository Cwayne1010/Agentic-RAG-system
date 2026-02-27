<script lang="ts">
	import { messages } from '$lib/stores/conversations';
	import MessageBubble from './MessageBubble.svelte';

	type ToolCall = {
		tool_name: string;
		args: object;
		status: 'running' | 'done';
		result?: object;
		children?: Array<{ tool_name: string; args: object; status: 'running' | 'done'; result?: object }>;
	};

	let { toolCalls = [] }: { toolCalls?: ToolCall[] } = $props();

	let scrollEl: HTMLDivElement | undefined = $state();

	$effect(() => {
		$messages;
		toolCalls;
		if (scrollEl) {
			scrollEl.scrollTop = scrollEl.scrollHeight;
		}
	});
</script>

<div bind:this={scrollEl} class="flex-1 overflow-y-auto p-4">
	<div class="mx-auto max-w-3xl">
		{#each $messages as message (message.id)}
			<MessageBubble {message} toolCalls={message.streaming ? toolCalls : []} />
		{/each}
	</div>
</div>
