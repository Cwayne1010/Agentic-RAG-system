<script lang="ts">
	import { onMount } from 'svelte';
	import { apiRequest, deleteConversation } from '$lib/api';
	import { conversations, activeConversationId, messages } from '$lib/stores/conversations';
	import { Button } from '$lib/components/ui/button';
	import { Separator } from '$lib/components/ui/separator';
	import { Trash2 } from '@lucide/svelte';
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

	async function removeConversation(id: string) {
		try {
			await deleteConversation(id);
			conversations.update((list) => list.filter((c) => c.id !== id));
			if ($activeConversationId === id) {
				activeConversationId.set(null);
				messages.set([]);
			}
		} catch (e) {
			console.error('Failed to delete conversation:', e);
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
	<!-- Nav links -->
	<div class="space-y-1 p-3">
		<a
			href="/"
			class="bg-accent flex w-full items-center rounded-md px-3 py-2 text-sm font-medium"
		>
			Chat
		</a>
		<a
			href="/documents"
			class="text-muted-foreground hover:bg-accent hover:text-foreground flex w-full items-center rounded-md px-3 py-2 text-sm transition-colors"
		>
			Documents
		</a>
	</div>

	<Separator />

	<!-- New chat -->
	<div class="p-3">
		<Button onclick={newConversation} class="w-full rounded-full" size="sm">
			+ New Chat
		</Button>
	</div>

	<Separator />

	<!-- Conversation list -->
	<div class="flex-1 overflow-y-auto py-2">
		{#each $conversations as conv (conv.id)}
			<div
				class="group flex items-center gap-1 px-3 py-2 transition-colors hover:bg-accent {$activeConversationId === conv.id
					? 'bg-accent'
					: ''}"
			>
				<button
					type="button"
					class="min-w-0 flex-1 truncate text-left text-sm {$activeConversationId === conv.id
						? 'font-medium'
						: 'text-muted-foreground'}"
					onclick={() => selectConversation(conv.id)}
				>
					{conv.title}
				</button>
				<button
					type="button"
					class="text-muted-foreground hover:text-destructive shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
					onclick={(e) => { e.stopPropagation(); removeConversation(conv.id); }}
					aria-label="Delete conversation"
				>
					<Trash2 class="h-3.5 w-3.5" />
				</button>
			</div>
		{/each}

		{#if $conversations.length === 0}
			<p class="text-muted-foreground px-3 py-4 text-center text-xs">No conversations yet</p>
		{/if}
	</div>

</div>
