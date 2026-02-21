<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { supabase } from '$lib/supabase';
	import { uploadDocument, listDocuments, deleteDocument } from '$lib/api';
	import { Button } from '$lib/components/ui/button';
	import { Separator } from '$lib/components/ui/separator';
	import FileUploadZone from '$lib/components/documents/FileUploadZone.svelte';
	import DocumentList from '$lib/components/documents/DocumentList.svelte';
	import EmbeddingModelSelector from '$lib/components/documents/EmbeddingModelSelector.svelte';
	import type { Document } from '../../types';

	let documents = $state<Document[]>([]);
	let uploading = $state(false);

	async function loadDocuments() {
		try {
			documents = await listDocuments();
		} catch (e) {
			toast.error('Failed to load documents');
		}
	}

	async function handleUpload(files: File[]) {
		uploading = true;
		for (const file of files) {
			try {
				const doc = await uploadDocument(file);
				documents = [doc, ...documents];
				toast.success(`Uploaded ${file.name}`);
			} catch (e) {
				toast.error(`Failed to upload ${file.name}: ${(e as Error).message}`);
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
		loadDocuments();

		let channel: ReturnType<typeof supabase.channel> | null = null;

		supabase.auth.getSession().then(({ data: { session } }) => {
			if (!session) return;
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

<div class="flex h-screen overflow-hidden">
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
		<div class="p-4">
			<Button
				onclick={() => supabase.auth.signOut()}
				variant="ghost"
				class="text-muted-foreground h-[44px] w-full"
			>
				Logout
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

			<div class="mb-6">
				<EmbeddingModelSelector />
			</div>

			<DocumentList {documents} ondelete={handleDelete} />
		</div>
	</div>
</div>
