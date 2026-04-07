<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { supabase } from '$lib/supabase';
	import { uploadDocument, deleteDocument } from '$lib/api';
	import { Button } from '$lib/components/ui/button';
	import { Separator } from '$lib/components/ui/separator';
	import { Settings } from '@lucide/svelte';
	import FileUploadZone from '$lib/components/documents/FileUploadZone.svelte';
	import DocumentList from '$lib/components/documents/DocumentList.svelte';
	import SettingsModal from '$lib/components/chat/SettingsModal.svelte';
	import type { Document } from '../../types';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let documents = $state<Document[]>(untrack(() => data.documents));
	let uploading = $state(false);
	let showSettings = $state(false);
	let currentUserId = $state('');

	async function handleUpload(files: File[]) {
		uploading = true;
		for (const file of files) {
			try {
				const doc = await uploadDocument(file);
				const wasUpdate = documents.some((d) => d.filename === file.name);
				// Remove stale entry in case this was an incremental update
				// (backend deleted the old doc, Realtime only fires on UPDATE not DELETE)
				documents = [doc, ...documents.filter((d) => d.filename !== file.name)];
				toast.success(wasUpdate ? `Updated ${file.name}` : `Uploaded ${file.name}`);
			} catch (e) {
				const msg = (e as Error).message;
				if (msg.startsWith('Duplicate:')) {
					// 409 — content already exists, show as warning not error
					toast.warning(msg);
				} else {
					toast.error(`Failed to upload ${file.name}: ${msg}`);
				}
			}
		}
		uploading = false;
	}

	async function handleDelete(id: string) {
		try {
			await deleteDocument(id);
			documents = documents.filter((d) => d.id !== id);
			toast.success('Document deleted');
		} catch (e) {
			toast.error('Failed to delete document');
		}
	}

	onMount(() => {
		let channel: ReturnType<typeof supabase.channel> | null = null;

		supabase.auth.getSession().then(({ data: { session } }) => {
			if (!session) return;
			currentUserId = session.user.id;
			channel = supabase
				.channel('documents-changes')
				.on(
					'postgres_changes',
					{
						event: 'UPDATE',
						schema: 'public',
						table: 'documents',
						filter: `user_id=eq.${session.user.id}`,
					},
					(payload) => {
						const updated = payload.new as Document;
						documents = documents.map((d) => (d.id === updated.id ? { ...d, ...updated } : d));
					},
				)
				.subscribe();
		});

		return () => {
			if (channel) supabase.removeChannel(channel);
		};
	});
</script>

<div class="flex h-screen overflow-hidden min-w-[768px]">
	<!-- Left sidebar: nav + logout -->
	<div class="flex h-full w-60 shrink-0 flex-col border-r bg-muted/30">
		<div class="space-y-1 p-3">
			<a
				href="/"
				class="text-muted-foreground hover:bg-accent hover:text-foreground flex w-full items-center rounded-md px-3 py-2 text-sm transition-colors"
			>
				Chat
			</a>
			<a
				href="/documents"
				class="bg-accent flex w-full items-center rounded-md px-3 py-2 text-sm font-medium"
			>
				Documents
			</a>
		</div>
		<Separator />
		<div class="flex-1"></div>
		<div class="flex items-center gap-2 p-4">
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
	</div>

	<!-- Main content -->
	<div class="flex flex-1 flex-col overflow-y-auto p-6">
		<div class="mx-auto w-full max-w-2xl">
			<h1 class="mb-6 text-xl font-semibold">Documents</h1>

			<div class="mb-4">
				<FileUploadZone onupload={handleUpload} disabled={uploading} />
				{#if uploading}
					<p class="text-muted-foreground mt-2 text-center text-xs">Uploading…</p>
				{/if}
			</div>

			<DocumentList {documents} ondelete={handleDelete} {currentUserId} />
		</div>
	</div>
</div>

{#if showSettings}
	<SettingsModal onclose={() => (showSettings = false)} />
{/if}
