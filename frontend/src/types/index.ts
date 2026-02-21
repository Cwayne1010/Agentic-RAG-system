export interface Conversation {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
}

export interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	created_at: string;
	streaming?: boolean; // ephemeral — true while assistant response is being streamed
}

export interface Document {
	id: string;
	filename: string;
	file_size: number;
	mime_type: string;
	status: 'pending' | 'processing' | 'completed' | 'failed';
	error_message?: string;
	chunk_count?: number;
	created_at: string;
	updated_at: string;
}
