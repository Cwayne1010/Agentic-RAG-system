<script lang="ts">
	import { onMount } from 'svelte';
	import { apiRequest } from '$lib/api';
	import { conversations, activeConversationId, messages } from '$lib/stores/conversations';
	import { Button } from '$lib/components/ui/button';
	import { Separator } from '$lib/components/ui/separator';
	import type { Conversation, Message } from '../../../types';

	async function loadConversations() {
		try {
			const data = await apiRequest<Conversation[]>('/api/conversations');
			conversations.set(data);
		} catch (e) {
			console.error('Failed to load conversations:', e);
		}
	}

	async function selectConversation(id: string) {
		activeConversationId.set(id);
		try {
			const data = await apiRequest<Message[]>(`/api/conversations/${id}/messages`);
			messages.set(data);
		} catch (e) {
			console.error('Failed to load messages:', e);
		}
	}

	async function newConversation() {
		try {
			const conv = await apiRequest<Conversation>('/api/conversations', {
				method: 'POST',
				body: JSON.stringify({ title: 'New Chat' }),
			});
			conversations.update((list) => [conv, ...list]);
			activeConversationId.set(conv.id);
			messages.set([]);
		} catch (e) {
			console.error('Failed to create conversation:', e);
		}
	}

	onMount(() => {
		loadConversations();
	});

	// Reload conversations list (e.g. after title update)
	export function refresh() {
		loadConversations();
	}
</script>

<div class="flex h-full w-60 flex-col border-r bg-muted/30">
	<!-- Header -->
	<div class="p-3">
		<Button onclick={newConversation} class="w-full" variant="outline" size="sm">
			+ New Chat
		</Button>
	</div>

	<Separator />

	<!-- Conversation list -->
	<div class="flex-1 overflow-y-auto py-2">
		{#each $conversations as conv (conv.id)}
			<button
				type="button"
				class="w-full truncate px-3 py-2 text-left text-sm transition-colors hover:bg-accent {$activeConversationId === conv.id
					? 'bg-accent font-medium'
					: 'text-muted-foreground'}"
				onclick={() => selectConversation(conv.id)}
			>
				{conv.title}
			</button>
		{/each}

		{#if $conversations.length === 0}
			<p class="text-muted-foreground px-3 py-4 text-center text-xs">No conversations yet</p>
		{/if}
	</div>

</div>
