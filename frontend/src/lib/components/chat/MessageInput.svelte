<script lang="ts">
	import { isStreaming } from '$lib/stores/conversations';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Plus } from '@lucide/svelte';

	let {
		onsend,
		onstop,
		fullContext = $bindable(false),
	}: { onsend: (message: string) => void; onstop: () => void; fullContext?: boolean } = $props();

	let text = $state('');
	let showPopover = $state(false);

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
	<div class="mx-auto flex w-full max-w-3xl flex-col gap-1.5">
		<!-- Helper text -->
		<div class="text-center">
			<p class="text-sm text-muted-foreground">What can I help you with?</p>
		</div>

		<div class="flex items-center gap-2">
			<!-- Context mode trigger -->
			<div class="relative shrink-0">
				<button
					onclick={() => (showPopover = !showPopover)}
					aria-label="Context mode"
					class="relative flex h-8 w-8 items-center justify-center rounded-full border transition-colors hover:bg-muted {fullContext
						? 'border-blue-500'
						: 'border-border'}"
				>
					<Plus class="h-4 w-4" />
				</button>

				{#if showPopover}
					<!-- Backdrop -->
					<button
						class="fixed inset-0 z-10 cursor-default"
						onclick={() => (showPopover = false)}
						tabindex="-1"
						aria-hidden="true"
					></button>

					<!-- Popover card -->
					<div class="absolute bottom-full left-0 z-20 mb-2 w-56 rounded-lg border bg-popover p-3 shadow-lg">
						<div class="flex items-start justify-between gap-3">
							<div>
								<p class="text-sm font-medium">Full context mode</p>
								<p class="mt-0.5 text-xs leading-snug text-muted-foreground">
									Evaluates every indexed document, not just top-k chunks.
								</p>
							</div>
							<button
								onclick={() => {
									fullContext = !fullContext;
									showPopover = false;
								}}
								class="mt-0.5 shrink-0 rounded-full px-2.5 py-1 text-xs font-medium transition-colors {fullContext
									? 'bg-blue-500 text-white hover:bg-blue-600'
									: 'border border-border text-muted-foreground hover:bg-muted'}"
							>
								{fullContext ? 'On' : 'Off'}
							</button>
						</div>
					</div>
				{/if}
			</div>

			<Textarea
				placeholder="Query your database…"
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

		<!-- Status line: always rendered to prevent layout shift, visible only when active -->
		<div class="flex items-center gap-2">
			<div class="w-8 shrink-0"></div>
			<div class="flex items-center gap-1.5 pl-3 text-xs text-blue-500 transition-opacity {fullContext ? 'opacity-100' : 'opacity-0'}">
				<span class="h-1 w-1 rounded-full bg-blue-500"></span>
				Full context mode active
			</div>
		</div>
	</div>
</div>
