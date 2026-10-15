import { useEffect, useRef, useState } from 'react';
import type { Design, Job, RevisionData } from './types';
import { connectRenderClient } from './renderClient';

export type Session = { designer: 'mcp' | 'codex'; token: string; authorized: boolean; codex_available: boolean; model: string; workspace: string; active_job: string | null };
const activeStates = new Set(['queued', 'generating', 'building', 'checking', 'repairing', 'exporting']);

export function useStudio() {
  const [session, setSession] = useState<Session | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [designs, setDesigns] = useState<Design[]>([]);
  const [design, setDesign] = useState<Design | null>(null);
  const [revision, setRevision] = useState<string | null>(null);
  const [data, setData] = useState<RevisionData | null>(null);
  const [latestData, setLatestData] = useState<RevisionData | null>(null);
  const [previous, setPrevious] = useState<RevisionData | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [isolated, setIsolated] = useState<string | null>(null);
  const [overlay, setOverlay] = useState(false);
  const stream = useRef<EventSource | null>(null);
  const token = useRef('');
  const current = useRef({ design, revision, job });
  current.current = { design, revision, job };
  const navigation = useRef(0);
  const mcpMode = session?.designer !== 'codex';
  const busy = !!job && activeStates.has(job.status);
  const historical = !!design && !!revision && revision !== design.display_revision && revision !== design.latest_revision;
  const report = historical ? data?.report : latestData?.report || data?.report;
  const reportRevision = historical ? revision : latestData?.revision || revision;

  async function api(url: string, body?: unknown) {
    const response = await fetch(url, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio-Token': token.current }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed');
    return result;
  }
  async function run(fn: () => Promise<void>) {
    setError('');
    try { await fn(); } catch (err) { setError((err as Error).message); }
  }
  async function loadRevision(designId: string, id: string) {
    const generation = navigation.current;
    const [result, d]: [RevisionData, Design] = await Promise.all([
      api(`/api/designs/${designId}/revisions/${id}`), api(`/api/designs/${designId}`),
    ]);
    const index = d.revisions.findIndex(row => row.id === id);
    const before = d.revisions.slice(0, index).reverse().find(row => row.scene);
    const baseline = before ? await api(`/api/designs/${designId}/revisions/${before.id}`) : null;
    if (generation !== navigation.current) return;
    setData(result); setRevision(id); setPrevious(baseline);
    setSelected(old => result.scene?.components.some(c => c.id === old) ? old : null);
  }
  async function refresh(id: string, display = true) {
    const generation = navigation.current;
    const d: Design = await api(`/api/designs/${id}`);
    const [list, latest] = await Promise.all([
      api('/api/designs'), d.latest_revision ? api(`/api/designs/${id}/revisions/${d.latest_revision}`) : null,
    ]);
    if (generation !== navigation.current) return;
    setDesign(d); setDesigns(list.designs); setLatestData(latest);
    const displayId = d.display_revision || d.latest_revision;
    if (display && displayId) await loadRevision(d.id, displayId);
  }
  function resetScene() {
    navigation.current++;
    setSelected(null); setHidden(new Set()); setIsolated(null); setOverlay(false);
    setData(null); setLatestData(null); setPrevious(null); setRevision(null);
  }
  function watch(next: Job) {
    stream.current?.close(); setJob(next);
    const events = new EventSource(`/api/jobs/${next.id}/events`);
    stream.current = events;
    events.onmessage = event => {
      const item = JSON.parse(event.data);
      if (item.type === 'status') {
        setJob(old => old ? { ...old, status: item.status } : null); setProgress(item.text);
        if (item.status === 'generating') void run(() => refresh(next.design_id, false));
      }
      if (item.type === 'revision') void run(() => refresh(next.design_id));
    };
    events.addEventListener('complete', () => {
      events.close();
      void run(async () => {
        setJob(await api(`/api/jobs/${next.id}`)); setProgress(''); await refresh(next.design_id);
      });
    });
    events.onerror = () => { if (events.readyState === EventSource.CLOSED) events.close(); };
  }
  useEffect(() => {
    void run(async () => {
      const s: Session = await api('/api/session'); token.current = s.token; setSession(s);
      const list = await api('/api/designs'); setDesigns(list.designs);
      const view = s.designer === 'mcp' ? await api('/api/viewer') : null;
      const initial = list.designs.find((d: Design) => d.id === view?.design_id)
        || list.designs.find((d: Design) => d.id === localStorage.getItem('studio-design')) || list.designs[0];
      if (initial) await refresh(initial.id);
      if (initial && view?.design_id === initial.id) {
        if (view.revision_id) await loadRevision(initial.id, view.revision_id);
        setSelected(view.selected?.[0] || null);
      }
      if (list.active_job) watch(await api(`/api/jobs/${list.active_job}`));
      setInitialized(true);
    });
    return () => stream.current?.close();
  }, []);
  useEffect(() => {
    if (!initialized || !session || !mcpMode) return;
    let closed = false, cursor = '', sequence: string | null = null;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const view = await api('/api/viewer');
        if (closed) return;
        const next = `${view.sequence}/${view.design_updated}`;
        if (view.design_id && next !== cursor) {
          if (current.current.design?.id !== view.design_id) resetScene();
          await refresh(view.design_id);
          if (view.sequence !== sequence && view.revision_id) await loadRevision(view.design_id, view.revision_id);
          cursor = next; sequence = view.sequence;
        }
        if (view.active_job && current.current.job?.id !== view.active_job) watch(await api(`/api/jobs/${view.active_job}`));
      } catch (err) { if (!closed) setError((err as Error).message); }
      if (!closed) timer = setTimeout(poll, 800);
    };
    void poll();
    return () => { closed = true; clearTimeout(timer); };
  }, [initialized, session?.designer]);
  useEffect(() => { if (design) localStorage.setItem('studio-design', design.id); }, [design?.id]);
  useEffect(() => {
    if (!initialized || !session) return;
    return connectRenderClient(session.token);
  }, [initialized, session?.token]);

  function selectComponent(id: string | null) {
    setSelected(id);
    if (mcpMode && design && revision) void run(async () => {
      await api('/api/viewer', { design_id: design.id, selected: id ? [id] : [], revision_id: revision });
    });
  }
  async function openDesign(d: Design) {
    if (busy) return;
    if (mcpMode) await api('/api/viewer', { design_id: d.id });
    resetScene(); setDesign(d); await refresh(d.id);
  }
  function startDraft() {
    if (busy) return;
    stream.current?.close(); resetScene(); setDesign(null); setJob(null); setProgress('');
  }
  async function showRevision(id: string) {
    if (!design) return;
    if (mcpMode) await api('/api/viewer', { design_id: design.id, revision_id: id });
    await loadRevision(design.id, id);
  }
  async function create(example?: string, savedId?: string, prompt = '') {
    const response = await api('/api/designs', { prompt, example, saved: savedId });
    resetScene(); setDesign(response.design); watch(response.job);
  }
  async function submit(prompt: string) {
    if (!prompt.trim() || busy || historical) return;
    if (!design) { await create(undefined, undefined, prompt); return; }
    const response = await api(`/api/designs/${design.id}/turns`, { prompt, selected: selected ? [selected] : [] });
    watch(response.job); await refresh(design.id, false);
  }
  async function rebuild() {
    if (design) watch((await api(`/api/designs/${design.id}/rebuild`, {})).job);
  }
  async function exportModel(format: string) {
    if (design) watch((await api(`/api/designs/${design.id}/export`, { format })).job);
  }
  async function cancel() { if (job) { await api(`/api/jobs/${job.id}/cancel`, {}); setProgress('Cancelling…'); } }
  async function authorize(enabled: boolean) { setSession(await api('/api/session', { authorize: enabled })); }
  function toggleHidden(id: string) {
    setHidden(old => { const next = new Set(old); next.has(id) ? next.delete(id) : next.add(id); return next; });
  }
  const fileUrl = (file: string, id = revision) => `/api/designs/${design?.id}/revisions/${id}/files/${file.split('/').map(encodeURIComponent).join('/')}`;
  return { session, designs, design, revision, data, previous, job, busy, progress, error, setError,
    selected, selectComponent, hidden, toggleHidden, isolated, setIsolated, overlay, setOverlay,
    mcpMode, historical, report, reportRevision, api, run, openDesign, startDraft, showRevision, create, submit,
    rebuild, exportModel, cancel, authorize, fileUrl };
}
