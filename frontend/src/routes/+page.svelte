<script lang="ts">
	import { get } from 'svelte/store';
	import { fade } from 'svelte/transition';
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
	let currentToolCalls = $state<Array<{
		tool_name: string;
		args: object;
		status: 'running' | 'done';
		result?: object;
		children?: Array<{ tool_name: string; args: object; status: 'running' | 'done'; result?: object }>;
	}>>([]);

	function handleStop() {
		abortController?.abort();
	}

	async function handleSend(message: string) {
		currentToolCalls = [];
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
				currentToolCalls = [];
				// Refresh sidebar to pick up any title update
				sidebarRef?.refresh();
			},
			// onError
			(err) => {
				messages.update((list) => list.filter((m) => m.id !== assistantId));
				isStreaming.set(false);
				abortController = null;
				currentToolCalls = [];
				toast.error(`Failed to send message: ${err}`);
			},
			abortController.signal,
			// onRetrieval
			({ chunk_count, sources }) => {
				if (chunk_count === 0) return;
				const sourceList = sources.length > 0 ? ` from ${sources.join(', ')}` : '';
				toast.info(`Retrieved ${chunk_count} chunk${chunk_count !== 1 ? 's' : ''}${sourceList}`, { duration: 3000 });
			},
			// onToolCall (add children: [])
			(data) => {
				currentToolCalls = [...currentToolCalls, {
					tool_name: data.tool_name, args: data.args, status: 'running', children: []
				}];
			},
			// onToolResult (unchanged)
			(data) => {
				currentToolCalls = currentToolCalls.map((tc) =>
					tc.tool_name === data.tool_name && tc.status === 'running'
						? { ...tc, status: 'done', result: data as object }
						: tc
				);
				setTimeout(() => {
					currentToolCalls = currentToolCalls.filter(
						(tc) => !(tc.tool_name === data.tool_name && tc.status === 'done')
					);
				}, 1500);
			},
			// onSubAgentStart
			(_data) => {},
			// onSubAgentToolCall — push child pill
			(data) => {
				currentToolCalls = currentToolCalls.map((tc) =>
					tc.tool_name === 'spawn_document_agent' && tc.status === 'running'
						? { ...tc, children: [...(tc.children ?? []), { tool_name: data.tool_name, args: data.args, status: 'running' }] }
						: tc
				);
			},
			// onSubAgentToolResult — mark child done
			(data) => {
				currentToolCalls = currentToolCalls.map((tc) => {
					if (tc.tool_name !== 'spawn_document_agent' || tc.status !== 'running') return tc;
					return {
						...tc,
						children: (tc.children ?? []).map((child) =>
							child.tool_name === data.tool_name && child.status === 'running'
								? { ...child, status: 'done', result: data as object }
								: child
						),
					};
				});
			},
			// onSubAgentDelta — no-op (parent pill spinner covers this)
			(_data) => {},
			// onSubAgentDone — mark parent done, remove after 2s
			(data) => {
				currentToolCalls = currentToolCalls.map((tc) =>
					tc.tool_name === 'spawn_document_agent' && tc.status === 'running'
						? { ...tc, status: 'done', result: { answer: data.answer } as object }
						: tc
				);
				setTimeout(() => {
					currentToolCalls = currentToolCalls.filter(
						(tc) => !(tc.tool_name === 'spawn_document_agent' && tc.status === 'done')
					);
				}, 2000);
			},
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

		<div class="relative flex flex-1 flex-col overflow-hidden">
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
			<Button
				onclick={() => (showSettings = true)}
				variant="ghost"
				class="text-muted-foreground h-[44px] w-[44px] shrink-0 px-0"
			>
				<Settings class="h-4 w-4" />
			</Button>
		</div>
		{#if $activeConversationId}
			<MessageInput onsend={handleSend} onstop={handleStop} showWelcome={false} />
		{:else}
			<div class="flex-1"></div>
		{/if}
	</div>
</div>

{#if currentToolCalls.length > 0}
	<div class="fixed right-4 bottom-12 flex flex-col items-end gap-1">
		{#each currentToolCalls as tc (tc.tool_name)}
			<div transition:fade={{ duration: 150 }} class="flex flex-col items-end gap-0.5">
				<span class="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs shadow-sm">
					{#if tc.status === 'running'}
						<span class="animate-spin inline-block text-muted-foreground">⟳</span>
					{:else}
						<span class="text-green-500">✓</span>
					{/if}
					<span class="text-muted-foreground">
						{tc.tool_name === 'retrieve_documents' ? 'Searching docs' :
						 tc.tool_name === 'web_search' ? 'Web search' :
						 tc.tool_name === 'query_database' ? 'Querying DB' :
						 tc.tool_name === 'spawn_document_agent' ? 'Document agent' : tc.tool_name}
						{#if (tc.result as {chunk_count?: number})?.chunk_count !== undefined} · {(tc.result as {chunk_count: number}).chunk_count} chunks{/if}
						{#if (tc.result as {row_count?: number})?.row_count !== undefined} · {(tc.result as {row_count: number}).row_count} rows{/if}
						{#if (tc.result as {result_count?: number})?.result_count !== undefined} · {(tc.result as {result_count: number}).result_count} results{/if}
					</span>
				</span>
				{#if tc.children && tc.children.length > 0}
					<div class="flex flex-col items-end gap-0.5 pr-3 border-r border-muted-foreground/20">
						{#each tc.children as child, i (child.tool_name + i)}
							<span class="inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-[10px] shadow-sm opacity-80">
								{#if child.status === 'running'}
									<span class="animate-spin inline-block text-muted-foreground">⟳</span>
								{:else}
									<span class="text-green-500">✓</span>
								{/if}
								<span class="text-muted-foreground">
									{child.tool_name === 'retrieve_documents' ? 'Sub-agent: searching docs' : child.tool_name}
									{#if (child.result as {chunk_count?: number})?.chunk_count !== undefined} · {(child.result as {chunk_count: number}).chunk_count} chunks{/if}
								</span>
							</span>
						{/each}
					</div>
				{/if}
			</div>
		{/each}
	</div>
{/if}

{#if showSettings}
	<SettingsModal onclose={() => (showSettings = false)} />
{/if}
