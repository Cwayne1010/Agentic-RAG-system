<script lang="ts">
	let { onupload, disabled = false }: { onupload: (files: File[]) => void; disabled?: boolean } =
		$props();

	let isDragging = $state(false);

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
		if (disabled) return;
		const files = Array.from(e.dataTransfer?.files ?? []).filter((f) => {
			const ext = f.name.split('.').pop()?.toLowerCase() ?? '';
			return (
				[
					'text/plain',
					'text/markdown',
					'application/pdf',
					'text/html',
					'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
				].includes(f.type) || ['txt', 'md', 'pdf', 'docx', 'html', 'htm'].includes(ext)
			);
		});
		if (files.length) onupload(files);
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (!disabled) isDragging = true;
	}

	function handleDragLeave() {
		isDragging = false;
	}

	function handleFileInput(e: Event) {
		const input = e.target as HTMLInputElement;
		const files = Array.from(input.files ?? []);
		if (files.length) onupload(files);
		input.value = '';
	}
</script>

<div
	class="rounded-lg border-2 border-dashed p-8 text-center transition-colors
		{isDragging
		? 'border-primary bg-primary/5'
		: 'border-muted-foreground/25 hover:border-muted-foreground/50'}
		{disabled ? 'opacity-50 cursor-not-allowed' : ''}"
	ondrop={handleDrop}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	role="region"
	aria-label="File upload zone"
>
	<div class="flex flex-col items-center gap-2">
		<svg
			xmlns="http://www.w3.org/2000/svg"
			class="text-muted-foreground h-8 w-8"
			fill="none"
			viewBox="0 0 24 24"
			stroke="currentColor"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
			/>
		</svg>
		<p class="text-sm font-medium">Drop files here</p>
		<p class="text-muted-foreground text-xs">PDF · DOCX · HTML · TXT · MD — max 10MB</p>
		<p class="text-muted-foreground text-xs">or</p>
		<label class="{disabled ? 'cursor-not-allowed' : 'cursor-pointer'}">
			<span
				class="bg-primary text-primary-foreground hover:bg-primary/90 inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
			>
				Browse files
			</span>
			<input
				type="file"
				accept=".txt,.md,.pdf,.docx,.html,.htm,text/plain,text/markdown,application/pdf,text/html,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
				multiple
				class="hidden"
				{disabled}
				onchange={handleFileInput}
			/>
		</label>
	</div>
</div>
