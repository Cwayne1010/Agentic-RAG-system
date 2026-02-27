import { supabase } from './supabase';
import type { Document } from '../types';

async function getAuthHeader(): Promise<string> {
	const { data } = await supabase.auth.getSession();
	const token = data.session?.access_token;
	if (!token) throw new Error('Not authenticated');
	return `Bearer ${token}`;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
	const authorization = await getAuthHeader();
	const res = await fetch(path, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			Authorization: authorization,
			...options.headers,
		},
	});
	if (!res.ok) {
		const text = await res.text();
		throw new Error(`API error ${res.status}: ${text}`);
	}
	return res.json();
}

export async function streamChat(
	conversationId: string,
	message: string,
	onDelta: (text: string) => void,
	onDone: () => void,
	onError: (err: string) => void,
	signal?: AbortSignal,
	onRetrieval?: (data: {
		chunk_count: number;
		sources: { name: string; chunks: number }[];
		mode?: string;
		doc_count?: number;
	}) => void,
	onToolCall?: (data: { tool_name: string; args: object }) => void,
	onToolResult?: (data: { tool_name: string; [key: string]: unknown }) => void,
	onSubAgentStart?: (data: { task: string; document_name: string | null }) => void,
	onSubAgentToolCall?: (data: { tool_name: string; args: object }) => void,
	onSubAgentToolResult?: (data: { tool_name: string; chunk_count: number; sources: { name: string; chunks: number }[] }) => void,
	onSubAgentDelta?: (data: { content: string }) => void,
	onSubAgentDone?: (data: { answer: string }) => void,
): Promise<void> {
	let authorization: string;
	try {
		authorization = await getAuthHeader();
	} catch (e) {
		onError(String(e));
		return;
	}

	let response: Response;
	try {
		response = await fetch(`/api/conversations/${conversationId}/messages`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: authorization,
				Accept: 'text/event-stream',
			},
			body: JSON.stringify({ message }),
			signal,
		});
	} catch (e) {
		if ((e as Error).name === 'AbortError') return;
		onError(String(e));
		return;
	}

	if (!response.ok) {
		onError(`HTTP ${response.status}`);
		return;
	}

	const reader = response.body!.getReader();
	const decoder = new TextDecoder();
	let buffer = '';
	let streamDone = false;

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;

			buffer += decoder.decode(value, { stream: true });
			const lines = buffer.split('\n');
			buffer = lines.pop() ?? '';

			for (const line of lines) {
				if (!line.startsWith('data: ')) continue;
				const data = JSON.parse(line.slice(6));
				if (data.type === 'retrieval') {
					onRetrieval?.({
						chunk_count: data.chunk_count,
						sources: data.sources ?? [],
						mode: data.mode,
						doc_count: data.doc_count,
					});
				} else if (data.type === 'tool_call') {
					onToolCall?.(data);
				} else if (data.type === 'tool_result') {
					onToolResult?.(data);
				} else if (data.type === 'sub_agent_start') {
					onSubAgentStart?.(data);
				} else if (data.type === 'sub_agent_scanning') {
					// no-op or forward to a callback — handled by parent pill spinner
				} else if (data.type === 'sub_agent_map_done') {
					// scanning progress event — actual answer comes via sub_agent_done
				} else if (data.type === 'sub_agent_tool_call') {
					onSubAgentToolCall?.(data);
				} else if (data.type === 'sub_agent_tool_result') {
					onSubAgentToolResult?.(data);
				} else if (data.type === 'sub_agent_delta') {
					onSubAgentDelta?.(data);
				} else if (data.type === 'sub_agent_done') {
					onSubAgentDone?.(data);
				} else if (data.type === 'delta') {
					onDelta(data.content);
				} else if (data.type === 'done') {
					streamDone = true;
					onDone();
				}
			}
		}
	} catch (e) {
		if ((e as Error).name === 'AbortError') return;
		onError(String(e));
		return;
	}

	// Stream ended without an explicit done event (proxy timeout, network drop, etc.)
	// Finalize the UI so it doesn't hang in streaming state indefinitely.
	if (!streamDone) {
		onDone();
	}
}

export async function uploadDocument(file: File): Promise<Document> {
	const authorization = await getAuthHeader();
	const formData = new FormData();
	formData.append('file', file);
	const res = await fetch('/api/documents/upload', {
		method: 'POST',
		headers: { Authorization: authorization },
		body: formData,
	});
	if (!res.ok) {
		const text = await res.text();
		let message: string;
		try {
			const body = JSON.parse(text);
			message = body.detail ?? `Upload failed (${res.status})`;
		} catch {
			message = text || `Upload failed (${res.status})`;
		}
		throw new Error(message);
	}
	return res.json();
}

export async function listDocuments(): Promise<Document[]> {
	return apiRequest<Document[]>('/api/documents');
}

export async function deleteDocument(id: string): Promise<void> {
	await apiRequest(`/api/documents/${id}`, { method: 'DELETE' });
}

export async function deleteConversation(id: string): Promise<void> {
	await apiRequest(`/api/conversations/${id}`, { method: 'DELETE' });
}

export interface MetadataField {
	name: string;
	type: 'string' | 'array' | 'date';
	description: string;
	allowed_values?: string[];
	nullable?: boolean;
}

export interface AppSettings {
	embedding_model: string;
	chat_model: string;
	map_model: string;
	embedding_locked: boolean;
	llm_base_url: string;
	llm_api_key: string;
	embedding_base_url: string;
	embedding_api_key: string;
	embedding_dimensions: number;
	business_description: string;
	topic_vocabulary: string[];
	metadata_schema: MetadataField[];
}

export async function getSettings(): Promise<AppSettings> {
	return apiRequest<AppSettings>('/api/settings');
}

export async function updateSettings(data: Partial<AppSettings>): Promise<AppSettings> {
	return apiRequest<AppSettings>('/api/settings', {
		method: 'PATCH',
		body: JSON.stringify(data),
	});
}

export async function generateVocabulary(
	business_description: string,
): Promise<{ vocabulary: string[] }> {
	return apiRequest('/api/settings/generate-vocabulary', {
		method: 'POST',
		body: JSON.stringify({ business_description }),
	});
}

export async function validateChatModel(
	model_id: string,
): Promise<{ valid: boolean; name?: string }> {
	return apiRequest('/api/settings/validate-model', {
		method: 'POST',
		body: JSON.stringify({ model_id }),
	});
}
