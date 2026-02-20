<script lang="ts">
	import { messages } from '$lib/stores/conversations';
	import MessageBubble from './MessageBubble.svelte';

	let scrollEl: HTMLDivElement | undefined = $state();

	$effect(() => {
		$messages;
		if (scrollEl) {
			scrollEl.scrollTop = scrollEl.scrollHeight;
		}
	});
</script>

<div bind:this={scrollEl} class="flex-1 overflow-y-auto p-4">
	{#if $messages.length === 0}
		<div class="flex h-full items-center justify-center">
			<p class="text-muted-foreground text-sm">Send a message to start the conversation</p>
		</div>
	{:else}
		{#each $messages as message (message.id)}
			<MessageBubble {message} />
		{/each}
	{/if}
</div>
