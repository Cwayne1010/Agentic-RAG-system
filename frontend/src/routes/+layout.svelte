<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { supabase } from '$lib/supabase';
	import { Toaster } from '$lib/components/ui/sonner';
	import AuthForm from '$lib/components/auth/AuthForm.svelte';
	import type { Session } from '@supabase/supabase-js';

	let { children } = $props();

	let session = $state<Session | null>(null);
	let loading = $state(true);

	onMount(() => {
		supabase.auth.getSession().then(({ data }) => {
			session = data.session;
			loading = false;
		});

		const {
			data: { subscription },
		} = supabase.auth.onAuthStateChange((_, s) => {
			session = s;
			loading = false;
		});

		return () => subscription.unsubscribe();
	});
</script>

<Toaster richColors />

{#if loading}
	<div class="flex h-screen items-center justify-center">
		<div class="text-muted-foreground text-sm">Loading…</div>
	</div>
{:else if session}
	{@render children()}
{:else}
	<AuthForm />
{/if}
