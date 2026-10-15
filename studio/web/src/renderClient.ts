/** Register this Studio tab; load WebGL capture code only on explicit requests. */
import type { CaptureRequest } from './renderView';

export function connectRenderClient(token: string): () => void {
  const clientId = crypto.randomUUID();
  let closed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let loaded: typeof import('./renderView') | null = null;
  const abort = new AbortController();
  async function post(path: string, body: unknown) {
    const response = await fetch(path, { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Studio-Token': token },
      body: JSON.stringify(body), signal: abort.signal });
    if (!response.ok) throw new Error('Studio render request ended');
    return response.json();
  }
  async function poll() {
    try {
      const { request }: { request: CaptureRequest | null } = await post('/api/renderers/poll', { client_id: clientId });
      if (closed) return;
      if (request) {
        const identity = { client_id: clientId, lease_token: request.lease_token,
          scene_fingerprint: request.scene_fingerprint };
        let result: { png_base64: string } | { error: string };
        try {
          loaded = await import('./renderView');
          result = { png_base64: await loaded.renderView(request) };
        } catch (error) {
          loaded?.disposeRenderer();
          result = { error: `Studio rendering unavailable: ${(error as Error).message}` };
        }
        if (!closed) await post(`/api/renders/${request.id}/result`, { ...identity, ...result });
      }
    } catch { /* A closed/expired capture must not change the user's UI state. */ }
    if (!closed) timer = setTimeout(poll, 1000);
  }
  void poll();
  return () => { closed = true; clearTimeout(timer); abort.abort(); loaded?.disposeRenderer(); };
}
