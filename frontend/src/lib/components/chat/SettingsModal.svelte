<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { X } from '@lucide/svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { getSettings, updateSettings, generateVocabulary, type AppSettings, type MetadataField } from '$lib/api';

	const REDACTED = '__REDACTED__';

	let { onclose }: { onclose: () => void } = $props();

	let settings: AppSettings | null = $state(null);
	let saving = $state(false);
	let activeTab = $state<'models' | 'knowledge' | 'schema'>('models');

	// LLM fields
	let chatModel = $state('');
	let mapModel = $state('');
	let llmBaseUrl = $state('');
	let llmApiKey = $state('');
	let llmApiKeySet = $state(false);

	// Embedding fields
	let embeddingModel = $state('');
	let embeddingBaseUrl = $state('');
	let embeddingApiKey = $state('');
	let embeddingApiKeySet = $state(false);
	let embeddingDimensions = $state(0);

	// Knowledge fields
	let businessDescription = $state('');
	let topicVocabulary = $state<string[]>([]);
	let generating = $state(false);
	let newTag = $state('');
	let tagsExpanded = $state(false);

	// Schema fields
	let metadataSchema = $state<MetadataField[]>([]);

	onMount(async () => {
		try {
			settings = await getSettings();
			chatModel = settings.chat_model;
			mapModel = settings.map_model;
			llmBaseUrl = settings.llm_base_url;
			llmApiKeySet = settings.llm_api_key === REDACTED;
			llmApiKey = '';
			embeddingModel = settings.embedding_model;
			embeddingBaseUrl = settings.embedding_base_url;
			embeddingApiKeySet = settings.embedding_api_key === REDACTED;
			embeddingApiKey = '';
			embeddingDimensions = settings.embedding_dimensions;
			businessDescription = settings.business_description ?? '';
			topicVocabulary = settings.topic_vocabulary ?? [];
			metadataSchema = settings.metadata_schema ?? [];
		} catch {
			toast.error('Failed to load settings');
		}
	});

	async function generate() {
		if (generating || !businessDescription.trim()) return;
		generating = true;
		try {
			const result = await generateVocabulary(businessDescription);
			topicVocabulary = result.vocabulary;
			toast.success(`Generated ${topicVocabulary.length} tags`);
		} catch (e) {
			toast.error(String(e));
		} finally {
			generating = false;
		}
	}

	function removeTag(tag: string) {
		topicVocabulary = topicVocabulary.filter((t) => t !== tag);
	}

	function addTag() {
		const slug = newTag.trim().toLowerCase().replace(/\s+/g, '-');
		if (!slug || topicVocabulary.includes(slug)) return;
		topicVocabulary = [...topicVocabulary, slug];
		newTag = '';
	}

	function addSchemaField() {
		metadataSchema = [...metadataSchema, { name: '', type: 'string', description: '', nullable: false }];
	}

	function removeSchemaField(index: number) {
		metadataSchema = metadataSchema.filter((_, i) => i !== index);
	}

	function updateSchemaField(index: number, patch: Partial<MetadataField>) {
		metadataSchema = metadataSchema.map((f, i) => (i === index ? { ...f, ...patch } : f));
	}

	function parseAllowedValues(raw: string): string[] {
		return raw.split(',').map((s) => s.trim()).filter(Boolean);
	}

	async function save() {
		if (saving) return;
		saving = true;
		try {
			const payload: Parameters<typeof updateSettings>[0] = {
				chat_model: chatModel,
				map_model: mapModel,
				llm_base_url: llmBaseUrl,
				embedding_model: embeddingModel,
				embedding_base_url: embeddingBaseUrl,
				embedding_dimensions: embeddingDimensions,
				business_description: businessDescription,
				topic_vocabulary: topicVocabulary,
				metadata_schema: metadataSchema,
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

</script>

<!-- Backdrop -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
	role="presentation"
	tabindex="-1"
>
	<!-- Panel -->
	<div
		role="dialog"
		aria-modal="true"
		aria-labelledby="settings-title"
		class="bg-background relative w-full max-w-lg rounded-xl border shadow-xl"
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b px-5 py-4">
			<h2 id="settings-title" class="text-sm font-semibold">Settings</h2>
			<button
				type="button"
				onclick={onclose}
				class="text-muted-foreground hover:text-foreground"
				aria-label="Close"
			>
				<X class="h-4 w-4" />
			</button>
		</div>

		<!-- Tabs -->
		<div class="flex border-b px-5">
			{#each [['models', 'Models'], ['knowledge', 'Knowledge'], ['schema', 'Schema']] as [id, label]}
				<button
					type="button"
					onclick={() => (activeTab = id as 'models' | 'knowledge' | 'schema')}
					class="mr-4 border-b-2 py-2.5 text-xs font-medium transition-colors {activeTab === id
						? 'border-foreground text-foreground'
						: 'border-transparent text-muted-foreground hover:text-foreground'}"
				>
					{label}
				</button>
			{/each}
		</div>

		{#if settings === null}
			<div class="flex h-[32rem] items-center justify-center text-sm text-muted-foreground">Loading…</div>
		{:else if activeTab === 'models'}
			<div class="h-[32rem] space-y-6 overflow-y-auto px-5 py-5">
				<!-- LLM Section -->
				<section>
					<h3 class="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">LLM</h3>
					<div class="space-y-3">
						<div>
							<label for="llm-model" class="mb-1 block text-xs text-muted-foreground">Model</label>
							<Input id="llm-model" bind:value={chatModel} placeholder="e.g. google/gemini-2.0-flash" class="h-8 text-sm" />
						</div>
						<div>
							<label for="map-model" class="mb-1 block text-xs text-muted-foreground">Map Model <span class="font-normal normal-case">(bulk doc analysis)</span></label>
							<Input id="map-model" bind:value={mapModel} placeholder="e.g. google/gemini-1.5-flash" class="h-8 text-sm" />
						</div>
						<div>
							<label for="llm-base-url" class="mb-1 block text-xs text-muted-foreground">Base URL</label>
							<Input id="llm-base-url" bind:value={llmBaseUrl} placeholder="https://openrouter.ai/api/v1" class="h-8 text-sm" />
						</div>
						<div>
							<label for="llm-api-key" class="mb-1 block text-xs text-muted-foreground">API Key</label>
							<Input id="llm-api-key" bind:value={llmApiKey} type="password" placeholder={llmApiKeySet ? 'Already set — enter new key to replace' : 'sk-or-…'} class="h-8 text-sm" />
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
							<label for="embedding-model" class="mb-1 block text-xs text-muted-foreground">Model</label>
							<Input
								id="embedding-model"
								bind:value={embeddingModel}
								placeholder="e.g. openai/text-embedding-3-small"
								disabled={settings.embedding_locked}
								class="h-8 text-sm"
							/>
						</div>
						<div>
							<label for="embedding-base-url" class="mb-1 block text-xs text-muted-foreground">Base URL</label>
							<Input
								id="embedding-base-url"
								bind:value={embeddingBaseUrl}
								placeholder="https://openrouter.ai/api/v1"
								disabled={settings.embedding_locked}
								class="h-8 text-sm"
							/>
						</div>
						<div>
							<label for="embedding-api-key" class="mb-1 block text-xs text-muted-foreground">API Key</label>
							<Input
								id="embedding-api-key"
								bind:value={embeddingApiKey}
								type="password"
								placeholder={embeddingApiKeySet ? 'Already set — enter new key to replace' : 'sk-or-…'}
								class="h-8 text-sm"
							/>
						</div>
						<div>
							<label for="embedding-dimensions" class="mb-1 block text-xs text-muted-foreground">Dimensions</label>
							<Input
								id="embedding-dimensions"
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
		{:else if activeTab === 'knowledge'}
			<div class="h-[32rem] space-y-5 overflow-y-auto px-5 py-5">
				<section>
					<h3 class="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Business Description</h3>
					<p class="mb-3 text-xs text-muted-foreground">Describe what this organisation does. A tailored tag vocabulary will be generated from this.</p>
					<textarea
						bind:value={businessDescription}
						placeholder="e.g. We are a logistics company managing freight forwarding, customs clearance, and last-mile delivery across Europe."
						rows="8"
						class="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring w-full rounded-md border px-3 py-2 text-sm text-muted-foreground focus-visible:ring-1 focus-visible:outline-none"
					></textarea>
					<Button
						size="sm"
						variant="outline"
						onclick={generate}
						disabled={generating || !businessDescription.trim()}
						class="mt-2"
					>
						{generating ? 'Generating…' : 'Generate Tags'}
					</Button>
				</section>

				<section>
					<h3 class="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tag Vocabulary</h3>
					<div class="mb-2 flex gap-2">
						<Input
							bind:value={newTag}
							placeholder="e.g. client-onboarding"
							class="h-8 text-sm"
							onkeydown={(e: KeyboardEvent) => e.key === 'Enter' && addTag()}
						/>
						<Button size="sm" variant="outline" onclick={addTag} disabled={!newTag.trim()}>Add</Button>
					</div>
					{#if topicVocabulary.length > 0}
						<button
							type="button"
							onclick={() => (tagsExpanded = !tagsExpanded)}
							class="text-muted-foreground hover:text-foreground mb-2 flex items-center gap-1 text-xs"
						>
							<span class="transition-transform {tagsExpanded ? 'rotate-90' : ''}">▶</span>
							{topicVocabulary.length} tags {tagsExpanded ? '— click any to remove' : ''}
						</button>
						{#if tagsExpanded}
							<div class="flex flex-wrap gap-1.5">
								{#each topicVocabulary as tag}
									<button
										type="button"
										onclick={() => removeTag(tag)}
										class="bg-muted hover:bg-destructive/10 hover:text-destructive rounded px-2 py-0.5 text-xs transition-colors"
									>
										{tag}
									</button>
								{/each}
							</div>
						{/if}
					{/if}
				</section>
			</div>
		{:else}
			<!-- Schema tab -->
			<div class="h-[32rem] overflow-y-auto px-5 py-5">
				<p class="mb-4 text-xs text-muted-foreground">
					Define the metadata fields extracted from each document at ingestion time. Changes apply to newly uploaded documents.
				</p>
				<div class="space-y-3">
					{#each metadataSchema as field, i}
						<div class="bg-muted/40 rounded-lg border p-3">
							<div class="mb-2 flex items-center gap-2">
								<Input
									value={field.name}
									oninput={(e) => updateSchemaField(i, { name: (e.target as HTMLInputElement).value })}
									placeholder="field_name"
									class="h-7 flex-1 text-xs"
								/>
								<select
									value={field.type}
									onchange={(e) => updateSchemaField(i, { type: (e.target as HTMLSelectElement).value as MetadataField['type'] })}
									class="border-input bg-background h-7 rounded-md border px-2 text-xs"
								>
									<option value="string">string</option>
									<option value="array">array</option>
									<option value="date">date</option>
								</select>
								<button
									type="button"
									onclick={() => removeSchemaField(i)}
									class="text-muted-foreground hover:text-destructive"
									aria-label="Remove field"
								>
									<X class="h-3.5 w-3.5" />
								</button>
							</div>
							<Input
								value={field.description}
								oninput={(e) => updateSchemaField(i, { description: (e.target as HTMLInputElement).value })}
								placeholder="Description / extraction instructions"
								class="mb-2 h-7 text-xs"
							/>
							{#if field.type === 'string'}
								<Input
									value={field.allowed_values?.join(', ') ?? ''}
									oninput={(e) => updateSchemaField(i, { allowed_values: parseAllowedValues((e.target as HTMLInputElement).value) })}
									placeholder="Allowed values (comma-separated, optional)"
									class="mb-2 h-7 text-xs"
								/>
							{/if}
							<label class="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
								<input
									type="checkbox"
									checked={field.nullable ?? false}
									onchange={(e) => updateSchemaField(i, { nullable: (e.target as HTMLInputElement).checked })}
									class="h-3 w-3"
								/>
								Nullable
							</label>
						</div>
					{/each}
				</div>
				<Button size="sm" variant="outline" onclick={addSchemaField} class="mt-3">+ Add Field</Button>
			</div>
		{/if}

		<!-- Footer -->
		<div class="flex justify-end gap-2 border-t px-5 py-4">
			<Button variant="ghost" size="sm" onclick={onclose}>Cancel</Button>
			<Button size="sm" onclick={save} disabled={saving}>
				{saving ? 'Saving…' : 'Save'}
			</Button>
		</div>
	</div>
</div>
