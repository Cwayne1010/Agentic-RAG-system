<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { X } from '@lucide/svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { getSettings, updateSettings, type AppSettings } from '$lib/api';

	const REDACTED = '__REDACTED__';

	let { onclose }: { onclose: () => void } = $props();

	let settings: AppSettings | null = $state(null);
	let saving = $state(false);

	// LLM fields
	let chatModel = $state('');
	let llmBaseUrl = $state('');
	let llmApiKey = $state('');
	let llmApiKeySet = $state(false);

	// Embedding fields
	let embeddingModel = $state('');
	let embeddingBaseUrl = $state('');
	let embeddingApiKey = $state('');
	let embeddingApiKeySet = $state(false);

	let embeddingDimensions = $state(0);

	onMount(async () => {
		try {
			settings = await getSettings();
			chatModel = settings.chat_model;
			llmBaseUrl = settings.llm_base_url;
			llmApiKeySet = settings.llm_api_key === REDACTED;
			llmApiKey = '';
			embeddingModel = settings.embedding_model;
			embeddingBaseUrl = settings.embedding_base_url;
			embeddingApiKeySet = settings.embedding_api_key === REDACTED;
			embeddingApiKey = '';
			embeddingDimensions = settings.embedding_dimensions;
		} catch {
			toast.error('Failed to load settings');
		}
	});

	async function save() {
		if (saving) return;
		saving = true;
		try {
			// Only send API keys if the user typed a new value; omit to preserve existing
			const payload: Parameters<typeof updateSettings>[0] = {
				chat_model: chatModel,
				llm_base_url: llmBaseUrl,
				embedding_model: embeddingModel,
				embedding_base_url: embeddingBaseUrl,
				embedding_dimensions: embeddingDimensions,
			};
			if (llmApiKey) payload.llm_api_key = llmApiKey;
			if (embeddingApiKey) payload.embedding_api_key = embeddingApiKey;

			settings = await updateSettings(payload);
			toast.success('Settings saved');
			onclose();
		} catch (e) {
			toast.error(String(e));
		} finally {
			saving = false;
		}
	}

	function handleBackdrop(e: MouseEvent) {
		if (e.target === e.currentTarget) onclose();
	}
</script>

<!-- Backdrop -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
	role="dialog"
	aria-modal="true"
	onclick={handleBackdrop}
>
	<!-- Panel -->
	<div class="bg-background relative w-full max-w-lg rounded-xl border shadow-xl">
		<!-- Header -->
		<div class="flex items-center justify-between border-b px-5 py-4">
			<h2 class="text-sm font-semibold">Settings</h2>
			<button
				type="button"
				onclick={onclose}
				class="text-muted-foreground hover:text-foreground"
				aria-label="Close"
			>
				<X class="h-4 w-4" />
			</button>
		</div>

		{#if settings === null}
			<div class="px-5 py-8 text-center text-sm text-muted-foreground">Loading…</div>
		{:else}
			<div class="space-y-6 px-5 py-5">
				<!-- LLM Section -->
				<section>
					<h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">LLM</h3>
					<div class="space-y-3">
						<div>
							<label class="mb-1 block text-xs text-muted-foreground">Model</label>
							<Input bind:value={chatModel} placeholder="e.g. google/gemini-2.0-flash" class="h-8 text-sm" />
						</div>
						<div>
							<label class="mb-1 block text-xs text-muted-foreground">Base URL</label>
							<Input bind:value={llmBaseUrl} placeholder="https://openrouter.ai/api/v1" class="h-8 text-sm" />
						</div>
						<div>
							<label class="mb-1 block text-xs text-muted-foreground">API Key</label>
							<Input bind:value={llmApiKey} type="password" placeholder={llmApiKeySet ? 'Already set — enter new key to replace' : 'sk-or-…'} class="h-8 text-sm" />
						</div>
					</div>
				</section>

				<hr class="border-border" />

				<!-- Embedding Section -->
				<section>
					<h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
						Embedding
						{#if settings.embedding_locked}
							<span class="ml-2 font-normal normal-case text-amber-500">Locked — delete all documents to change</span>
						{/if}
					</h3>
					<div class="space-y-3">
						<div>
							<label class="mb-1 block text-xs text-muted-foreground">Model</label>
							<Input
								bind:value={embeddingModel}
								placeholder="e.g. openai/text-embedding-3-small"
								disabled={settings.embedding_locked}
								class="h-8 text-sm"
							/>
						</div>
						<div>
							<label class="mb-1 block text-xs text-muted-foreground">Base URL</label>
							<Input
								bind:value={embeddingBaseUrl}
								placeholder="https://openrouter.ai/api/v1"
								disabled={settings.embedding_locked}
								class="h-8 text-sm"
							/>
						</div>
						<div>
							<label class="mb-1 block text-xs text-muted-foreground">API Key</label>
							<Input
								bind:value={embeddingApiKey}
								type="password"
								placeholder={embeddingApiKeySet ? 'Already set — enter new key to replace' : 'sk-or-…'}
								class="h-8 text-sm"
							/>
						</div>
						<div>
							<label class="mb-1 block text-xs text-muted-foreground">Dimensions</label>
							<Input
								bind:value={embeddingDimensions}
								type="number"
								min="1"
								placeholder="e.g. 1024"
								disabled={settings.embedding_locked}
								class="h-8 text-sm [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
							/>
						</div>
					</div>
				</section>
			</div>

			<!-- Footer -->
			<div class="flex justify-end gap-2 border-t px-5 py-4">
				<Button variant="ghost" size="sm" onclick={onclose}>Cancel</Button>
				<Button size="sm" onclick={save} disabled={saving}>
					{saving ? 'Saving…' : 'Save'}
				</Button>
			</div>
		{/if}
	</div>
</div>
