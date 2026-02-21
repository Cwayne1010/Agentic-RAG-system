<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Button } from '$lib/components/ui/button';
	import { getSettings, updateSettings, type AppSettings } from '$lib/api';

	const EMBEDDING_MODELS = [
		{ id: 'text-embedding-3-small', label: 'text-embedding-3-small' },
		{ id: 'text-embedding-3-large', label: 'text-embedding-3-large (Matryoshka →1536d)' },
	];

	let settings: AppSettings | null = $state(null);
	let embeddingModel = $state('');
	let saving = $state(false);

	const dirty = $derived(settings !== null && embeddingModel !== settings.embedding_model);

	onMount(async () => {
		try {
			settings = await getSettings();
			embeddingModel = settings.embedding_model;
		} catch {
			toast.error('Failed to load model settings');
		}
	});

	async function save() {
		if (!dirty || saving) return;
		saving = true;
		try {
			settings = await updateSettings({ embedding_model: embeddingModel });
			embeddingModel = settings.embedding_model;
			toast.success('Embedding model saved');
		} catch (e) {
			toast.error(String(e));
		} finally {
			saving = false;
		}
	}
</script>

<div class="flex items-center gap-2 text-xs">
	<span class="text-muted-foreground whitespace-nowrap">Embedding model:</span>
	<select
		bind:value={embeddingModel}
		disabled={!settings || settings.embedding_locked}
		class="border-input bg-background h-7 rounded-md border px-2 py-0 text-xs disabled:cursor-not-allowed disabled:opacity-50"
		title={settings?.embedding_locked
			? 'Locked — documents already ingested. Delete all documents to change.'
			: ''}
	>
		{#each EMBEDDING_MODELS as m}
			<option value={m.id}>{m.label}</option>
		{/each}
	</select>
	<Button
		onclick={save}
		size="sm"
		class="h-7 px-3 text-xs"
		disabled={!dirty || saving || settings?.embedding_locked}
	>
		{saving ? 'Saving…' : 'Save'}
	</Button>
	{#if settings?.embedding_locked}
		<span class="text-muted-foreground text-xs">Locked — delete all documents to change</span>
	{/if}
</div>
