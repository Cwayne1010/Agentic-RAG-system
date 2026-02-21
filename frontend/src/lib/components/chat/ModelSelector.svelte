<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getSettings, updateSettings, type AppSettings } from '$lib/api';

	// All route through OpenRouter — only OPENROUTER_API_KEY needed
	const CHAT_MODELS = [
		{ id: 'google/gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
		{ id: 'google/gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
		{ id: 'anthropic/claude-3-5-haiku', label: 'Claude 3.5 Haiku' },
		{ id: 'anthropic/claude-3-5-sonnet', label: 'Claude 3.5 Sonnet' },
		{ id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
		{ id: 'openai/gpt-4o', label: 'GPT-4o' },
		{ id: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B' },
	];

	const STORAGE_KEY = 'chat_model';

	let settings: AppSettings | null = $state(null);
	let chatModel = $state(localStorage.getItem(STORAGE_KEY) ?? CHAT_MODELS[0].id);
	let saving = $state(false);

	onMount(async () => {
		try {
			settings = await getSettings();
			chatModel = settings.chat_model;
			localStorage.setItem(STORAGE_KEY, chatModel);
		} catch {
			toast.error('Failed to load model settings');
		}
	});

	async function save() {
		if (saving || !settings || chatModel === settings.chat_model) return;
		saving = true;
		try {
			settings = await updateSettings({ chat_model: chatModel });
			chatModel = settings.chat_model;
			localStorage.setItem(STORAGE_KEY, chatModel);
		} catch (e) {
			toast.error(String(e));
		} finally {
			saving = false;
		}
	}
</script>

<select
	bind:value={chatModel}
	onchange={save}
	disabled={saving}
	class="border-input bg-background text-muted-foreground h-9 shrink-0 rounded-full border px-3 py-0 text-xs disabled:cursor-not-allowed disabled:opacity-50"
>
	{#each CHAT_MODELS as m}
		<option value={m.id}>{m.label}</option>
	{/each}
</select>
