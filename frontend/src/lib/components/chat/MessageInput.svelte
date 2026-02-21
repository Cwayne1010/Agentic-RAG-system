<script lang="ts">
	import { isStreaming } from '$lib/stores/conversations';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';
	import ModelSelector from './ModelSelector.svelte';

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
	<div class="mx-auto flex w-full max-w-3xl flex-col gap-2">
		<div class="flex items-center gap-2">
			<Textarea
				placeholder="Send a message…"
				bind:value={text}
				onkeydown={handleKeydown}
				disabled={$isStreaming}
				rows={1}
				class="min-h-[44px] resize-none rounded-full py-3"
			/>
			{#if $isStreaming}
				<Button onclick={onstop} variant="destructive" class="shrink-0 rounded-full">
					Stop
				</Button>
			{:else}
				<Button onclick={submit} disabled={!text.trim()} class="shrink-0 rounded-full !bg-black !text-white hover:!bg-black/80 disabled:!bg-black/60">
					Send
				</Button>
			{/if}
		</div>
		<div class="flex justify-start">
			<ModelSelector />
		</div>
	</div>
</div>
