export interface Conversation {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
}

export interface ToolCall {
	tool_name: string;
	args: object;
	status: 'running' | 'done';
	result?: object;
	children?: ToolCall[];
}

export interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	created_at: string;
	streaming?: boolean; // ephemeral — true while assistant response is being streamed
	toolCalls?: ToolCall[]; // persisted after streaming ends
	toolCallOffset?: number; // content length when first tool call fired — splits pre/post text
}

export interface DocumentMetadata {
	doc_type: string;
	language: string;
	topics: string[];
	summary: string;
	entities: string[];
	date: string | null;
}

export interface Document {
	id: string;
	user_id: string;
	filename: string;
	file_size: number;
	mime_type: string;
	status: 'pending' | 'parsing' | 'processing' | 'completed' | 'failed';
	error_message?: string;
	chunk_count?: number;
	chunks_total?: number;
	chunks_processed?: number;
	metadata?: DocumentMetadata;
	created_at: string;
	updated_at: string;
}
