import { supabase } from './supabase';

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
				if (data.type === 'delta') {
					onDelta(data.content);
				} else if (data.type === 'done') {
					onDone();
				}
			}
		}
	} catch (e) {
		if ((e as Error).name === 'AbortError') return;
		onError(String(e));
	}
}
