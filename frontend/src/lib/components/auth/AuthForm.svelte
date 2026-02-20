<script lang="ts">
	import { supabase } from '$lib/supabase';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';

	let mode = $state<'login' | 'signup'>('login');
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let info = $state('');
	let loading = $state(false);

	async function handleSubmit(e: Event) {
		e.preventDefault();
		loading = true;
		error = '';
		info = '';

		try {
			if (mode === 'login') {
				const { error: err } = await supabase.auth.signInWithPassword({ email, password });
				if (err) error = err.message;
			} else {
				const { error: err } = await supabase.auth.signUp({ email, password });
				if (err) error = err.message;
				else info = 'Check your email to confirm your account.';
			}
		} finally {
			loading = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-background p-4">
	<div class="w-full max-w-sm space-y-6">
		<div class="text-center">
			<h1 class="text-2xl font-bold">Agentic RAG</h1>
			<p class="text-muted-foreground text-sm">Your AI assistant</p>
		</div>

		<!-- Tab toggle -->
		<div class="flex rounded-lg border p-1">
			<button
				type="button"
				class="flex-1 rounded-md py-1.5 text-sm font-medium transition-colors {mode === 'login'
					? 'bg-primary text-primary-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				onclick={() => { mode = 'login'; error = ''; info = ''; }}
			>
				Login
			</button>
			<button
				type="button"
				class="flex-1 rounded-md py-1.5 text-sm font-medium transition-colors {mode === 'signup'
					? 'bg-primary text-primary-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				onclick={() => { mode = 'signup'; error = ''; info = ''; }}
			>
				Sign Up
			</button>
		</div>

		<form onsubmit={handleSubmit} class="space-y-4">
			<div class="space-y-2">
				<label class="text-sm font-medium" for="email">Email</label>
				<Input
					id="email"
					type="email"
					placeholder="you@example.com"
					bind:value={email}
					required
					disabled={loading}
				/>
			</div>

			<div class="space-y-2">
				<label class="text-sm font-medium" for="password">Password</label>
				<Input
					id="password"
					type="password"
					placeholder="••••••••"
					bind:value={password}
					required
					disabled={loading}
				/>
			</div>

			{#if error}
				<p class="text-destructive text-sm">{error}</p>
			{/if}

			{#if info}
				<p class="text-muted-foreground text-sm">{info}</p>
			{/if}

			<Button type="submit" class="w-full" disabled={loading}>
				{loading ? 'Please wait…' : mode === 'login' ? 'Login' : 'Create Account'}
			</Button>
		</form>
	</div>
</div>
