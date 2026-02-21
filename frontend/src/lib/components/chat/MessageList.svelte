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
	<div class="mx-auto max-w-3xl">
		{#each $messages as message (message.id)}
			<MessageBubble {message} />
		{/each}
	</div>
</div>
