import { writable } from 'svelte/store';
import type { Conversation, Message } from '../../types';

export const conversations = writable<Conversation[]>([]);
export const activeConversationId = writable<string | null>(null);
export const messages = writable<Message[]>([]);
export const isStreaming = writable(false);
