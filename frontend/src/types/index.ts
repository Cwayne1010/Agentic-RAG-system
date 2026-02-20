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
