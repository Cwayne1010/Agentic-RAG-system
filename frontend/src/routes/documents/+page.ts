import { listDocuments } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	const documents = await listDocuments();
	return { documents };
};
