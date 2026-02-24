<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { streamChat, apiRequest } from '$lib/api';
	import { supabase } from '$lib/supabase';
	import { conversations, activeConversationId, messages, isStreaming } from '$lib/stores/conversations';
	import ChatSidebar from '$lib/components/chat/ChatSidebar.svelte';
	import MessageList from '$lib/components/chat/MessageList.svelte';
	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import SettingsModal from '$lib/components/chat/SettingsModal.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Settings } from '@lucide/svelte';
	import type { Conversation } from '../types';

	let sidebarRef: ChatSidebar | undefined = $state();
	let abortController: AbortController | null = null;
	let showSettings = $state(false);

	function handleStop() {
		abortController?.abort();
	}

	async function handleSend(message: string) {
		let conversationId = get(activeConversationId);

		// Auto-create a conversation if none is active
		if (!conversationId) {
			try {
				const conv = await apiRequest<Conversation>('/api/conversations', {
					method: 'POST',
					body: JSON.stringify({ title: 'New Chat' }),
				});
				conversations.update((list) => [conv, ...list]);
				activeConversationId.set(conv.id);
				messages.set([]);
				conversationId = conv.id;
			} catch (e) {
				toast.error('Failed to create conversation.');
				return;
			}
		}

		// 1. Optimistically add user message
		const userMsg = {
			id: crypto.randomUUID(),
			role: 'user' as const,
			content: message,
			created_at: new Date().toISOString(),
		};
		messages.update((list) => [...list, userMsg]);

		// 2. Add streaming assistant placeholder
		const assistantId = crypto.randomUUID();
		const assistantMsg = {
			id: assistantId,
			role: 'assistant' as const,
			content: '',
			created_at: new Date().toISOString(),
			streaming: true,
		};
		messages.update((list) => [...list, assistantMsg]);
		isStreaming.set(true);

		// 3. Stream response
		abortController = new AbortController();
		await streamChat(
			conversationId,
			message,
			// onDelta
			(text) => {
				messages.update((list) =>
					list.map((m) => (m.id === assistantId ? { ...m, content: m.content + text } : m)),
				);
			},
			// onDone
			() => {
				messages.update((list) =>
					list.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
				);
				isStreaming.set(false);
				abortController = null;
				// Refresh sidebar to pick up any title update
				sidebarRef?.refresh();
			},
			// onError
			(err) => {
				messages.update((list) => list.filter((m) => m.id !== assistantId));
				isStreaming.set(false);
				abortController = null;
				toast.error(`Failed to send message: ${err}`);
			},
			abortController.signal,
		);

		// If aborted mid-stream, finalise the partial message
		if (abortController?.signal.aborted) {
			messages.update((list) =>
				list.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
			);
			isStreaming.set(false);
			abortController = null;
		}
	}
</script>

<div class="flex h-screen flex-col overflow-hidden">
	<!-- Top area: sidebar + messages -->
	<div class="flex min-h-0 flex-1 overflow-hidden">
		<ChatSidebar bind:this={sidebarRef} />

		<div class="flex flex-1 flex-col overflow-hidden">
			{#if $activeConversationId}
				<MessageList />
			{:else}
				<div class="flex flex-1 items-center justify-center">
					<MessageInput onsend={handleSend} onstop={handleStop} />
				</div>
			{/if}
		</div>
	</div>

	<!-- Bottom bar: spans full width, aligns sidebar footer with chat input -->
	<div class="flex shrink-0">
		<div class="flex w-60 shrink-0 items-center gap-2 border-r p-4">
			<Button
				onclick={() => supabase.auth.signOut()}
				variant="ghost"
				class="text-muted-foreground h-[44px] flex-1"
			>
				Logout
			</Button>
			<button onclick={() => (showSettings = true)} class="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-full">
				<Settings class="h-4 w-4" />
			</button>
		</div>
		{#if $activeConversationId}
			<MessageInput onsend={handleSend} onstop={handleStop} />
		{:else}
			<div class="flex-1"></div>
		{/if}
	</div>
</div>

{#if showSettings}
	<SettingsModal onclose={() => (showSettings = false)} />
{/if}
