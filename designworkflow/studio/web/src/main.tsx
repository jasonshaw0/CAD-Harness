import { useEffect, useRef, useState } from 'react';

import { createRoot } from 'react-dom/client';

import { Box, Boxes, Plus, ArrowUp, ArrowDownToLine, ChevronDown, ChevronRight, Circle, Check, X, LoaderCircle, Eye, EyeOff, Focus, Layers2, Rotate3D, PanelRightClose, Square, Sparkles, Command, ShieldCheck, FileCode2, AlertCircle, Maximize2, Clock3, Triangle, FolderOpen, Cable } from 'lucide-react';

import Viewer, { type ViewerControl } from './Viewer';

import type { Design, Job, RevisionData, ComponentMesh } from './types';

import './style.css';



type Session = { token: string; authorized: boolean; codex_available: boolean; model: string; active_job: string | null };

const activeStates = new Set(['queued', 'generating', 'building', 'checking', 'repairing', 'exporting']);

function App() {

  const [session, setSession] = useState<Session | null>(null);

  const [designs, setDesigns] = useState<Design[]>([]);

  const [design, setDesign] = useState<Design | null>(null);

  const [revision, setRevision] = useState<string | null>(null);

  const [data, setData] = useState<RevisionData | null>(null);

  const [latestData, setLatestData] = useState<RevisionData | null>(null);

  const [previous, setPrevious] = useState<RevisionData | null>(null);

  const [job, setJob] = useState<Job | null>(null);

  const [progress, setProgress] = useState('');

  const [prompt, setPrompt] = useState('');

  const [error, setError] = useState('');

  const [selected, setSelected] = useState<string | null>(null);

  const [hidden, setHidden] = useState<Set<string>>(new Set());

  const [isolated, setIsolated] = useState<string | null>(null);

  const [overlay, setOverlay] = useState(false);

  const [ghost, setGhost] = useState(true);

  const [showChecks, setShowChecks] = useState(false);

  const [showOpen, setShowOpen] = useState(false);

  const [saved, setSaved] = useState<{id: string; title: string; outcome: string}[]>([]);

  const [checkFilter, setCheckFilter] = useState('all');

  const controls = useRef<ViewerControl | null>(null);

  const stream = useRef<EventSource | null>(null);

  const bottom = useRef<HTMLDivElement>(null);

  const current = useRef({design, revision}); current.current = {design, revision};

  const busy = !!job && activeStates.has(job.status);

  const scene = data?.scene || null;

  const historical = !!design && !!revision && revision !== design.display_revision && revision !== design.latest_revision;

  const report = historical ? data?.report : latestData?.report || data?.report;

  const reportRevision = historical ? revision : latestData?.revision || revision;

  const api = async (url: string, body?: unknown) => {

    const response = await fetch(url, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio-Token': session?.token || '' }, body: JSON.stringify(body) });

    const result = await response.json(); if (!response.ok) throw new Error(result.error || 'Request failed'); return result;

  };

  const run = async (fn: () => Promise<void>) => { setError(''); try { await fn(); } catch (err) { setError(String((err as Error).message)); } };

  const reloadList = async () => { const list = await api('/api/designs'); setDesigns(list.designs); };

  const loadRevision = async (designId: string, id: string) => {

    const result = await api(`/api/designs/${designId}/revisions/${id}`); setData(result); setRevision(id);

    const d = await api(`/api/designs/${designId}`) as Design;

    const index = d.revisions.findIndex(row => row.id === id);

    const before = d.revisions.slice(0, index).reverse().find(row => row.scene);

    setPrevious(before ? await api(`/api/designs/${designId}/revisions/${before.id}`) : null);

  };

  const refresh = async (id: string, display = true) => {

    const d: Design = await api(`/api/designs/${id}`); setDesign(d); await reloadList();

    setLatestData(d.latest_revision ? await api(`/api/designs/${id}/revisions/${d.latest_revision}`) : null);

    if (display && d.display_revision) await loadRevision(d.id, d.display_revision);

    return d;

  };

  const watch = (next: Job) => {

    stream.current?.close(); setJob(next);

    const events = new EventSource(`/api/jobs/${next.id}/events`); stream.current = events;

    events.onmessage = event => { const item = JSON.parse(event.data); if (item.type === 'status') { setJob(old => old ? {...old, status: item.status} : null); setProgress(item.text); } if (item.type === 'revision') void refresh(next.design_id); };

    events.addEventListener('complete', () => { events.close(); void run(async () => { const final = await api(`/api/jobs/${next.id}`); setJob(final); setProgress(''); await refresh(next.design_id); }); });

    events.onerror = () => { if (events.readyState === EventSource.CLOSED) events.close(); };

  };

  useEffect(() => { void run(async () => { const s = await api('/api/session'); setSession(s); const list = await api('/api/designs'); setDesigns(list.designs); const preferred = localStorage.getItem('studio-design'); const initial = list.designs.find((d: Design) => d.id === preferred) || list.designs[0]; if (initial) await refresh(initial.id); if (list.active_job) watch(await api(`/api/jobs/${list.active_job}`)); }); return () => stream.current?.close(); }, []);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [design?.messages.length, progress]);

  useEffect(() => { if (design) localStorage.setItem('studio-design', design.id); }, [design?.id]);

  const openDesign = (d: Design) => run(async () => { if (busy) return; setHidden(new Set()); setSelected(null); setIsolated(null); setOverlay(false); setLatestData(null); setData(null); setPrevious(null); setRevision(null); await refresh(d.id); });

  const create = (example?: string, savedId?: string) => run(async () => { const response = await api('/api/designs', { prompt, example, saved: savedId }); setDesign(response.design); setLatestData(null); setData(null); setPrevious(null); setRevision(null); setPrompt(''); setSelected(null); setHidden(new Set()); setIsolated(null); setShowOpen(false); watch(response.job); });

  const submit = () => run(async () => { if (!prompt.trim() || busy) return; if (!design) { await create(); return; } if (historical) return; const response = await api(`/api/designs/${design.id}/turns`, { prompt, selected: selected ? [selected] : [] }); setPrompt(''); watch(response.job); await refresh(design.id, false); });

  const toggleHidden = (id: string) => setHidden(old => { const next = new Set(old); next.has(id) ? next.delete(id) : next.add(id); return next; });

  const downloadUrl = (file: string) => `/api/designs/${design!.id}/revisions/${revision}/files/${file}`;

  const exportModel = (format: string) => run(async () => { const response = await api(`/api/designs/${design!.id}/export`, { format }); watch(response.job); });

  const passed = report?.coverage.filter(row => row.status === 'pass').length || 0;

  const unresolved = report?.coverage.filter(row => row.status !== 'pass').length || 0;

  const selectedMesh: ComponentMesh | undefined = scene?.components.find(c => c.id === selected);



  return <div className="app-shell">

    <header className="topbar"><div className="brand"><span className="brand-mark"><Boxes size={19}/></span><b>cadHarness</b><span className="brand-divider"/><span className="studio-label">STUDIO</span></div><div className="top-context"><span className="local-dot"/>Local workspace<span className="top-slash">/</span>{design?.title || 'New design'}</div><button className="session-status" onClick={() => run(async () => setSession(await api('/api/session', {authorize: !session?.authorized})))}><ShieldCheck size={14}/>{session?.authorized ? 'Trusted session' : 'Session locked'}</button></header>

    <aside className="sidebar">

      <div className="workspace-heading"><span>WORKSPACE</span><button title="Open saved workflow" aria-label="Open saved workflow" onClick={() => run(async () => { setSaved((await api('/api/library')).saved); setShowOpen(true); })}><FolderOpen size={15}/></button></div>

      <button className="new-design" disabled={busy} onClick={() => {setDesign(null);setLatestData(null);setData(null);setPrevious(null);setRevision(null);setSelected(null);setPrompt('');}}><Plus size={15}/>New design</button>

      <div className="design-list">{designs.map(d => <button key={d.id} disabled={busy && d.id !== design?.id} className={`design-item ${design?.id === d.id ? 'active' : ''}`} onClick={() => void openDesign(d)}><Box size={15}/><span>{d.title}</span><span className={`tiny-dot ${d.status}`}/></button>)}</div>

      <div className="sidebar-rule"/><div className="workspace-heading"><span>COMPONENTS</span><span>{scene?.components.length || '—'}</span></div>

      <div className="component-list">{scene ? scene.components.map(component => <div className={`component-row ${selected === component.id ? 'selected' : ''}`} key={component.id}><button className="component-name" onClick={() => setSelected(selected === component.id ? null : component.id)}><ChevronRight size={12}/>{component.role === 'reference-envelope' ? <Cable size={15}/> : <Box size={15}/>}<span>{component.id}</span></button><button aria-label={`${hidden.has(component.id) ? 'Show' : 'Hide'} ${component.id}`} title="Toggle visibility" onClick={() => toggleHidden(component.id)}>{hidden.has(component.id) ? <EyeOff size={13}/> : <Eye size={13}/>}</button></div>) : <p className="sidebar-hint">Your model's parts will appear here.</p>}</div>

      {selectedMesh && <div className="selection-card"><span className="eyebrow">SELECTED COMPONENT</span><strong>{selectedMesh.id}</strong><p>{selectedMesh.bounds.size_mm.map(n => +n.toFixed(2)).join(' × ')} mm</p><button onClick={() => setIsolated(isolated ? null : selectedMesh.id)}><Focus size={13}/>{isolated ? 'Show all parts' : 'Isolate part'}</button></div>}

      <div className="sidebar-bottom"><span className="version">PROTOTYPE · 0.1</span><p>Native geometry.<br/>Editable Python. Measured checks.</p></div>

    </aside>

    <main className="model-workspace">

      <div className="model-toolbar"><div className="view-label"><Box size={14}/><span>{revision || 'DESIGN CANVAS'}</span>{historical && <span className="historical">History</span>}</div><div className="view-actions"><button title="Rebuild current source" aria-label="Rebuild current source" disabled={busy || historical || !design?.latest_revision || !session?.authorized} onClick={() => void run(async () => {const response = await api(`/api/designs/${design!.id}/rebuild`, {});watch(response.job);})}><Rotate3D size={15}/></button><button title="Fit model" aria-label="Fit model" onClick={() => controls.current?.fit()}><Maximize2 size={15}/></button><div className="toolbar-divider"/>{['iso','top','front','right'].map(view => <button className="view-text" key={view} onClick={() => controls.current?.view(view)}>{view}</button>)}<div className="toolbar-divider"/><button title="Ghost reference envelopes" aria-label="Ghost reference envelopes" className={ghost ? 'on' : ''} onClick={() => setGhost(!ghost)}><Boxes size={15}/></button><button disabled={!previous?.scene} title="Overlay previous revision" aria-label="Overlay previous revision" className={overlay ? 'on' : ''} onClick={() => setOverlay(!overlay)}><Layers2 size={15}/></button></div></div>

      <div className="canvas-area"><Viewer scene={scene} previous={previous?.scene || null} selected={selected} hidden={hidden} isolated={isolated} overlay={overlay} ghost={ghost} onSelect={setSelected} controls={controls}/>

        {!scene && <div className="canvas-empty"><div className="empty-cube"><Box size={54} strokeWidth={0.7}/></div><span className="eyebrow">FROM INTENT TO GEOMETRY</span><h1>A space to shape<br/>your next idea.</h1><p>Describe a part to the designer, or start<br/>with a source-backed example.</p><div className="example-buttons"><button disabled={!session?.authorized || busy} onClick={() => void create('square-mount')}><Box size={16}/><span>Mounting plate</span><ChevronRight size={14}/></button><button disabled={!session?.authorized || busy} onClick={() => void create('enclosure')}><Boxes size={16}/><span>Enclosure</span><ChevronRight size={14}/></button><button disabled={!session?.authorized || busy} onClick={() => void create('flange')}><Circle size={16}/><span>Flange</span><ChevronRight size={14}/></button></div></div>}

        {busy && <div className="build-toast"><LoaderCircle className="spin" size={15}/>{progress || 'Preparing design…'}</div>}

        {design && !busy && (['failed','cancelled','interrupted'].includes(design.status) || design.latest_revision !== design.display_revision) && <div className="failure-toast"><AlertCircle size={15}/>{design.status === 'needs-revision' ? 'Latest build needs attention' : design.status === 'failed' ? 'Design job failed' : design.status}. {revision ? `Showing ${revision}.` : 'No geometry available.'}</div>}

        <div className="axis-label"><span className="axis-z">Z</span><span className="axis-y">Y</span><span className="axis-x">X</span><span>mm · Z up</span></div>

        {overlay && <div className="overlay-key"><i/>Previous revision<span/>Current revision</div>}

      </div>

      <div className="revision-bar"><span className="eyebrow">REVISIONS</span><div className="revision-list">{design?.revisions.map(row => <button title={row.summary} key={row.id} disabled={!row.scene} onClick={() => void run(async () => loadRevision(design.id, row.id))} className={revision === row.id ? 'active' : ''}><span className={`tiny-dot ${row.status}`}/>{row.id}</button>)}{!design?.revisions.length && <span className="muted">Every change, preserved.</span>}</div>{historical && <button className="return-latest" onClick={() => void run(async () => { if (design?.display_revision) await loadRevision(design.id, design.display_revision); })}>Return to current</button>}</div>

      <div className="evidence-bar"><button className="evidence-summary" onClick={() => setShowChecks(!showChecks)}><span className={`check-symbol ${report?.ready_for_review ? 'pass' : ''}`}>{report?.ready_for_review ? <Check size={14}/> : <Circle size={12}/>}</span><strong>{report ? `${passed}/${report.coverage.length} checks` : 'No checks yet'}</strong><span>{report?.ready_for_review ? (unresolved ? `Ready · ${unresolved} unverified` : 'Ready for review') : unresolved ? `${unresolved} need attention` : 'Evidence appears after a build'}</span><ChevronDown className={showChecks ? 'flip' : ''} size={14}/></button><div className="evidence-right">{report && <span><Clock3 size={12}/>{report.elapsed_seconds.toFixed(1)}s</span>}<span className="physical-gap">Physical fit unverified</span></div></div>

      {showChecks && <section className="checks-panel"><div className="checks-header"><strong>Measured requirements · {reportRevision}</strong><div>{['all','attention'].map(filter => <button className={checkFilter === filter ? 'active' : ''} key={filter} onClick={() => setCheckFilter(filter)}>{filter === 'all' ? 'All checks' : 'Needs attention'}</button>)}</div><button aria-label="Close checks" onClick={() => setShowChecks(false)}><X size={15}/></button></div><div className="checks-scroll">{data?.comparison && <details className="revision-changes"><summary>Changes since {data.comparison.baseline}</summary><p>Geometry: {[...Object.keys(data.comparison.components.changed), ...data.comparison.components.added].join(', ') || 'unchanged'}{data.comparison.components.removed.length ? `; removed ${data.comparison.components.removed.join(', ')}` : ''}</p><p>Requirements: {[...Object.keys(data.comparison.requirements.modified), ...data.comparison.requirements.added].map(id => id.replace('workflow.', '')).join(', ') || 'unchanged'}{data.comparison.requirements.removed.length ? `; removed ${data.comparison.requirements.removed.join(', ')}` : ''}</p><small>Geometry identities and recorded criteria; overlay is not an exact solid difference.</small></details>}{report?.assumptions.length ? <details className="revision-changes"><summary>Design assumptions</summary>{report.assumptions.map((item, i) => <p key={i}>{item.description}</p>)}</details> : null}{report?.coverage.filter(row => checkFilter === 'all' || row.status !== 'pass').map(row => <details className="check-row" key={row.id}><summary><span className={`status-dot ${row.status}`}/><span>{row.description}</span><small>{row.status}</small></summary><p>{row.reason}</p>{row.result && <div className="check-values"><span>ACTUAL <code>{JSON.stringify(row.result.actual)} {row.result.unit}</code></span><span>EXPECTED <code>{JSON.stringify(row.result.expected)}</code></span></div>}</details>)}{report?.errors.map((text,index) => <p className="check-error" key={index}>{text}</p>)}{!report && <p className="muted">Build a design to see measured evidence.</p>}</div></section>}

    </main>

    <aside className="designer-panel"><div className="designer-heading"><span className="designer-icon"><Sparkles size={16}/></span><strong>Designer</strong><span className="model-tag">CODEX</span></div><div className="conversation">

      {!design?.messages.length && <div className="conversation-intro"><h2>What are we making?</h2><p>Describe the geometry, dimensions, and what it needs to fit. I'll build it and check the result.</p><div className="prompt-suggestion" onClick={() => setPrompt('Create a 70 × 40 × 5 mm mounting plate with four Ø4.5 mm through-holes on a centered 50 × 20 mm rectangle.')} role="button" tabIndex={0} onKeyDown={event => {if(event.key === 'Enter') setPrompt('Create a 70 × 40 × 5 mm mounting plate with four Ø4.5 mm through-holes on a centered 50 × 20 mm rectangle.');}}><span>TRY A FIRST DESIGN</span><p>A mounting plate with four holes and precise dimensions.</p><ArrowUp size={14}/></div><div className="capability"><FileCode2 size={14}/><p>Real build123d Python.<br/><span>Source stays yours to edit.</span></p></div></div>}

      {design?.messages.map((message,index) => <article className={`message ${message.role} ${message.kind || ''}`} key={index}>{message.role === 'assistant' && <span className="message-author"><Sparkles size={12}/>DESIGNER{message.revision && <b>{message.revision}</b>}</span>}<p>{message.text}</p>{message.questions?.length ? <ul>{message.questions.map(q => <li key={q}>{q}</li>)}</ul> : null}</article>)}

      {busy && <div className="working-message"><LoaderCircle className="spin" size={13}/><span>{progress || 'Working…'}</span></div>}

      <div ref={bottom}/></div>

      {error && <div className="inline-error"><AlertCircle size={14}/><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={13}/></button></div>}

      {selected && <div className="selection-context"><Box size={12}/>{selected}<button aria-label="Clear selection" onClick={() => setSelected(null)}><X size={12}/></button></div>}

      <div className="composer"><textarea aria-label="Describe your design" placeholder={historical ? 'Return to the current revision to continue' : design ? 'Describe a change…' : 'Describe a part. Include dimensions…'} value={prompt} disabled={busy || historical || !session?.authorized} onChange={event => setPrompt(event.target.value)} onKeyDown={event => { if(event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {event.preventDefault();void submit();} }}/><div className="composer-bottom"><span>{busy ? 'Building your design' : 'Ctrl ↵ to send'}</span>{busy ? <button aria-label="Cancel job" title="Cancel" className="send cancel" onClick={() => void run(async () => {await api(`/api/jobs/${job!.id}/cancel`, {});setProgress('Cancelling…');})}><Square size={12}/></button> : <button className="send" aria-label="Send design request" disabled={!prompt.trim() || !session?.authorized || historical} onClick={() => void submit()}><ArrowUp size={17}/></button>}</div></div>

      <div className="designer-footer"><span className="local-dot"/>{session?.model || 'Connecting to local workspace'}</div>

      {data && <div className="downloads"><a href={`/api/designs/${design!.id}/revisions/${revision}/source`}><FileCode2 size={13}/>Source</a><a href={`/api/designs/${design!.id}/revisions/${reportRevision}/files/run.json`}><ShieldCheck size={13}/>Report</a><button disabled={busy || !report?.ready_for_review || historical || revision !== design?.latest_revision} onClick={() => void exportModel('step')}><ArrowDownToLine size={13}/>STEP</button><button disabled={busy || !report?.ready_for_review || historical || revision !== design?.latest_revision} onClick={() => void exportModel('stl')}>STL</button>{data.files.filter(file => /exports\/(step|stl)\/.*\.(step|stl)$/.test(file)).map(file => <a key={file} className="export-link" href={downloadUrl(file)} download><ArrowDownToLine size={12}/>{file.endsWith('.step') ? 'Download STEP' : 'Download STL'} · {file.split('/').pop()?.replace(/\.(step|stl)$/, '')}</a>)}</div>}

    </aside>

    {!session?.authorized && session && <div className="session-banner"><ShieldCheck size={19}/><div><strong>Enable your local design session</strong><p>Let the designer generate and run Python on this computer. Local execution is not sandboxed.</p></div><button onClick={() => void run(async () => setSession(await api('/api/session', {authorize:true})))}>Enable session<ChevronRight size={14}/></button></div>}

    {showOpen && <div className="modal-backdrop" onClick={() => setShowOpen(false)}><section className="open-modal" onClick={event => event.stopPropagation()}><div className="checks-header"><strong>Open a saved workflow</strong><button aria-label="Close saved workflows" onClick={() => setShowOpen(false)}><X size={16}/></button></div><p>A local copy will be built in Studio. Original source stays intact.</p><div className="saved-list">{saved.length ? saved.map(item => <button key={item.id} disabled={busy || !session?.authorized} onClick={() => void create(undefined, item.id)}><FolderOpen size={15}/><span>{item.title}</span><small>{item.outcome}</small></button>) : <p>No saved workflow runs found.</p>}</div></section></div>}

  </div>;

}



createRoot(document.getElementById('root')!).render(<App/>);

