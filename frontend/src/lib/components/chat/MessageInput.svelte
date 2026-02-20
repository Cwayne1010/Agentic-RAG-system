<script lang="ts">
	import { isStreaming } from '$lib/stores/conversations';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';

	let { onsend, onstop }: { onsend: (message: string) => void; onstop: () => void } = $props();

	let text = $state('');

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			submit();
		}
	}

	function submit() {
		const trimmed = text.trim();
		if (!trimmed || $isStreaming) return;
		onsend(trimmed);
		text = '';
	}
</script>

<div class="flex-1 p-4">
	<div class="flex gap-2">
		<Textarea
			placeholder="Send a message… (Enter to send, Shift+Enter for newline)"
			bind:value={text}
			onkeydown={handleKeydown}
			disabled={$isStreaming}
			rows={1}
			class="min-h-[44px] resize-none"
		/>
		{#if $isStreaming}
			<Button onclick={onstop} variant="destructive" class="shrink-0">
				Stop
			</Button>
		{:else}
			<Button onclick={submit} disabled={!text.trim()} class="shrink-0">
				Send
			</Button>
		{/if}
	</div>
</div>
