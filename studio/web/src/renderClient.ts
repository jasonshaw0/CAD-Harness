/** Register this Studio tab; load WebGL capture code only on explicit requests. */
import type { CaptureRequest } from './renderView';

export const RENDER_PROTOCOL = 'cadharness-studio-render/1';

class RenderHTTPError extends Error {
  status: number;
  constructor(status: number) { super(`Studio render HTTP ${status}`); this.status = status; }
}

export function connectRenderClient(token: string, protocol?: string): () => void {
  // A new static bundle can be served by an old, still-running Python owner.
  // Do not probe unsupported POST routes once a second indefinitely.
  if (protocol !== RENDER_PROTOCOL) return () => {};
  const clientId = crypto.randomUUID();
  let closed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let loaded: typeof import('./renderView') | null = null;
  let retryDelay = 1000;
  const abort = new AbortController();
  async function post(path: string, body: unknown) {
    const response = await fetch(path, { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Studio-Token': token },
      body: JSON.stringify(body), signal: abort.signal });
    if (!response.ok) throw new RenderHTTPError(response.status);
    return response.json();
  }
  async function poll() {
    try {
      const { request }: { request: CaptureRequest | null } = await post('/api/renderers/poll', { client_id: clientId });
      retryDelay = 1000;
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
    } catch (error) {
      if (error instanceof RenderHTTPError && [401, 403, 404, 405, 410, 426].includes(error.status)) {
        closed = true;
        loaded?.disposeRenderer();
        console.warn(`Studio image capture stopped (HTTP ${error.status}). Restart the Studio owner after updating cadHarness, then reload this tab.`);
      } else {
        // Temporary disconnects retry without changing the user's viewport.
        retryDelay = Math.min(retryDelay * 2, 10000);
      }
    }
    if (!closed) timer = setTimeout(poll, retryDelay);
  }
  void poll();
  return () => { closed = true; clearTimeout(timer); abort.abort(); loaded?.disposeRenderer(); };
}
