<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { streamChat } from '$lib/api';
	import { supabase } from '$lib/supabase';
	import { conversations, activeConversationId, messages, isStreaming } from '$lib/stores/conversations';
	import ChatSidebar from '$lib/components/chat/ChatSidebar.svelte';
	import MessageList from '$lib/components/chat/MessageList.svelte';
	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import { Button } from '$lib/components/ui/button';

	let sidebarRef: ChatSidebar | undefined = $state();
	let abortController: AbortController | null = null;

	function handleStop() {
		abortController?.abort();
	}

	async function handleSend(message: string) {
		const conversationId = get(activeConversationId);
		if (!conversationId) {
			toast.error('Please select or create a conversation first.');
			return;
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
					<div class="text-center">
						<p class="text-muted-foreground text-sm">Select a conversation or create a new one</p>
					</div>
				</div>
			{/if}
		</div>
	</div>

	<!-- Bottom bar: spans full width, aligns sidebar footer with chat input -->
	<div class="flex shrink-0">
		<div class="flex w-60 shrink-0 items-center border-r p-4">
			<Button
				onclick={() => supabase.auth.signOut()}
				variant="ghost"
				class="text-muted-foreground h-[44px] w-full"
			>
				Logout
			</Button>
		</div>
		{#if $activeConversationId}
			<MessageInput onsend={handleSend} onstop={handleStop} />
		{:else}
			<div class="flex-1"></div>
		{/if}
	</div>
</div>
