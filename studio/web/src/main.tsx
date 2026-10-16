import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowDownToLine, ArrowUp, Box, Boxes, Check, CheckCircle2, ChevronDown, ChevronRight, Code2, Columns2, Download, Expand, Eye, EyeOff, FileCode2, FolderOpen, Focus, Grid2X2, History, Info, Layers2, LoaderCircle, Moon, MousePointer2, PanelLeft, PanelLeftClose, Plus, RotateCcw, Search, Settings2, ShieldCheck, SlidersHorizontal, Sparkles, Square, Sun, X, AlertCircle } from 'lucide-react';
import Viewer, { type ViewerControl } from './Viewer';
import { Empty, IconButton, Modal, Note, Pane, Section } from './components';
import { useStudio } from './useStudio';
import './style.css';

type Panel = 'properties' | 'review' | 'history' | 'compare' | 'activity' | 'source' | 'settings' | 'session';
type Theme = 'light' | 'dark' | 'system';
type Preferences = { theme: Theme; grid: boolean; axes: boolean; edges: boolean; ghost: boolean };
const defaults: Preferences = { theme: 'light', grid: false, axes: true, edges: true, ghost: true };
function storedPreferences(): Preferences {
  try {
    const saved = JSON.parse(localStorage.getItem('studio-preferences') || '{}');
    return { theme: ['light', 'dark', 'system'].includes(saved.theme) ? saved.theme : 'light',
      ...Object.fromEntries(['grid', 'axes', 'edges', 'ghost'].map(key => [key, typeof saved[key] === 'boolean' ? saved[key] : defaults[key as keyof Preferences]])) } as Preferences;
  } catch { return defaults; }
}
const titleCase = (value: string) => value.replaceAll('-', ' ').replace(/^./, x => x.toUpperCase());
const number = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 3 });
const views = [['iso', 'Isometric'], ['top', 'Top'], ['front', 'Front'], ['right', 'Right'], ['left', 'Left'], ['bottom', 'Bottom']];

function App() {
  const s = useStudio();
  const [panel, setPanel] = useState<Panel | null>(null);
  const [explorer, setExplorer] = useState(true);
  const [searchExplorer, setSearchExplorer] = useState(false);
  const [query, setQuery] = useState('');
  const [menu, setMenu] = useState<'view' | 'inspect' | 'export' | null>(null);
  const [modal, setModal] = useState<'new' | 'library' | 'commands' | null>(null);
  const [saved, setSaved] = useState<{ id: string; title: string; outcome: string }[]>([]);
  const [commandQuery, setCommandQuery] = useState('');
  const [preferences, setPreferences] = useState(storedPreferences);
  const [systemDark, setSystemDark] = useState(() => matchMedia('(prefers-color-scheme: dark)').matches);
  const [view, setView] = useState('iso');
  const [focusMode, setFocusMode] = useState(false);
  const [filter, setFilter] = useState('all');
  const [sourceFile, setSourceFile] = useState('');
  const [sourceText, setSourceText] = useState('');
  const [sourceError, setSourceError] = useState('');
  const [prompt, setPrompt] = useState('');
  const controls = useRef<ViewerControl | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const theme = preferences.theme === 'system' ? systemDark ? 'dark' : 'light' : preferences.theme;
  const scene = s.data?.scene || null;
  const component = scene?.components.find(item => item.id === s.selected);
  const rows = s.report?.coverage || [];
  const passed = rows.filter(row => row.status === 'pass').length;
  const failed = rows.filter(row => row.status === 'fail' || row.status === 'error').length;
  const unknown = rows.length - passed - failed;
  const canExport = !!s.design && !!s.report?.ready_for_review && !s.busy && !s.historical && s.revision === s.design.latest_revision && !!s.session?.authorized;
  const canRebuild = !!s.design?.latest_revision && !s.busy && !s.historical && !!s.session?.authorized;
  const sourceFiles = s.data?.files.filter(file => /^project\//.test(file) && /\.(py|toml)$/.test(file) && !/^project\/(evidence|exports|inspector|previews)\//.test(file)) || [];
  const exports = s.data?.files.filter(file => /exports\/(step|stl)\/.*\.(step|stl)$/.test(file)) || [];
  const sourceBundle = `/api/designs/${s.design?.id}/revisions/${s.revision}/source`;
  const needsAttention = !!s.design && !s.busy && (['failed', 'cancelled', 'interrupted', 'needs-revision'].includes(s.design.status) || s.design.latest_revision !== s.design.display_revision);

  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const change = () => setSystemDark(media.matches);
    media.addEventListener('change', change); return () => media.removeEventListener('change', change);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#192228' : '#ffffff');
    localStorage.setItem('studio-preferences', JSON.stringify(preferences));
  }, [preferences, theme]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, [s.design?.messages.length, s.progress, panel]);
  useEffect(() => {
    if (!sourceFiles.includes(sourceFile)) setSourceFile(sourceFiles[0] || '');
  }, [s.data]);
  useEffect(() => {
    if (panel !== 'source' || !sourceFile || !s.revision) return;
    const abort = new AbortController(); setSourceText(''); setSourceError('');
    void fetch(s.fileUrl(sourceFile), { signal: abort.signal }).then(async response => {
      if (!response.ok) throw new Error('Source file could not be loaded.');
      const text = await response.text(); if (!abort.signal.aborted) setSourceText(text);
    }).catch(err => { if (!abort.signal.aborted) setSourceError(err.message); });
    return () => abort.abort();
  }, [sourceFile, s.design?.id, s.revision, panel]);

  function openPanel(next: Panel) { setPanel(next); setMenu(null); setFocusMode(false); }
  function pick(id: string | null) { s.selectComponent(id); if (id) openPanel('properties'); }
  function setPreference<K extends keyof Preferences>(key: K, value: Preferences[K]) { setPreferences(old => ({ ...old, [key]: value })); }
  function changeView(next: string) { controls.current?.view(next); setView(next); setMenu(null); }
  function toggleMenu(next: typeof menu) { setMenu(old => old === next ? null : next); }
  function newDesign() { setModal('new'); setMenu(null); }
  function openLibrary() { void s.run(async () => { setSaved((await s.api('/api/library')).saved); setModal('library'); }); }
  function startExample(example: string) { void s.run(async () => { await s.create(example); setModal(null); setPanel(null); }); }
  function resetCamera() { controls.current?.fit(); setView('iso'); setMenu(null); }
  const commands = [
    { name: 'Toggle project explorer', key: 'E', icon: <PanelLeft size={16}/>, action: () => setExplorer(old => !old) },
    { name: 'Component properties', key: 'I', icon: <SlidersHorizontal size={16}/>, action: () => openPanel('properties') },
    { name: 'Engineering checks', key: 'R', icon: <CheckCircle2 size={16}/>, action: () => openPanel('review') },
    { name: 'Revision history', key: 'H', icon: <History size={16}/>, action: () => openPanel('history') },
    { name: 'Compare revisions', key: 'C', icon: <Columns2 size={16}/>, action: () => openPanel('compare') },
    { name: 'Source files', key: '', icon: <FileCode2 size={16}/>, action: () => openPanel('source') },
    { name: 'Agent activity', key: 'A', icon: <Activity size={16}/>, action: () => openPanel('activity') },
    { name: 'Viewport settings', key: '', icon: <Settings2 size={16}/>, action: () => openPanel('settings') },
    { name: 'Fit viewport', key: 'F', icon: <Focus size={16}/>, action: resetCamera },
    { name: 'Distraction-free mode', key: 'D', icon: <Expand size={16}/>, action: () => setFocusMode(old => !old) },
    { name: 'Toggle construction grid', key: 'G', icon: <Grid2X2 size={16}/>, action: () => setPreference('grid', !preferences.grid) },
    { name: 'New design', key: '', icon: <Plus size={16}/>, action: newDesign },
  ];
  const keyboard = useRef({ commands, close: () => { setMenu(null); setPanel(null); }, palette: () => { setCommandQuery(''); setModal(old => old === 'commands' ? null : 'commands'); } });
  keyboard.current = { commands, close: () => { setMenu(null); setPanel(null); }, palette: () => { setCommandQuery(''); setModal(old => old === 'commands' ? null : 'commands'); } };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); keyboard.current.palette(); return; }
      if ((event.target as HTMLElement).closest('input, textarea, select, dialog, [contenteditable="true"]') || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === 'Escape') { keyboard.current.close(); return; }
      const command = keyboard.current.commands.find(item => item.key.toLowerCase() === event.key.toLowerCase());
      if (command && command.key) { event.preventDefault(); command.action(); }
    };
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey);
  }, []);

  const panelInfo: Record<Panel, [string, string]> = {
    properties: ['Component inspector', 'Properties'], review: ['Engineering evidence', 'Design review'],
    history: ['Design lineage', 'Revision history'], compare: ['Changes over time', 'Compare revisions'],
    activity: [s.mcpMode ? 'IDE assistant · MCP' : 'Codex CLI designer', 'Agent activity'],
    source: ['Editable design authority', 'Source files'], settings: ['Make space for your work', 'Workspace preferences'],
    session: ['Local execution', 'Session status'],
  };
  function panelContent() {
    if (panel === 'properties') return component ? <>
      <span className="eyebrow">Selected component</span><h3 className="hero-name">{component.id}</h3>
      <div className="tag-row"><span className="tag blue"><Box size={12}/>{component.role}</span><span className="tag">{s.hidden.has(component.id) ? 'Hidden' : 'Visible'}</span></div>
      <div className="property-grid">{['X', 'Y', 'Z'].map((axis, index) => <div className="metric-tile" key={axis}><span>{axis} · Size</span><b>{number(component.bounds.size_mm[index])}</b><small>mm</small></div>)}</div>
      <h4>Geometry <Box size={14}/></h4>
      <dl className="properties"><div><dt>Bounding box minimum</dt><dd>{component.bounds.min_mm.map(number).join(', ')} mm</dd></div><div><dt>Bounding box maximum</dt><dd>{component.bounds.max_mm.map(number).join(', ')} mm</dd></div><div><dt>Volume</dt><dd>{number(component.volume_mm3)} mm³</dd></div><div><dt>Source fingerprint</dt><dd><code title={component.fingerprint}>{component.fingerprint.slice(0, 16)}…</code></dd></div></dl>
      <h4>Quick actions <Focus size={14}/></h4><div className="action-row"><button className={`soft-action ${s.isolated === component.id ? 'active' : ''}`} onClick={() => s.setIsolated(s.isolated ? null : component.id)}><Focus size={14}/>{s.isolated ? 'Show all parts' : 'Isolate part'}</button><button className="soft-action" onClick={() => s.toggleHidden(component.id)}>{s.hidden.has(component.id) ? <Eye size={14}/> : <EyeOff size={14}/>}{s.hidden.has(component.id) ? 'Show part' : 'Hide part'}</button></div>
      <h4>Review context <ShieldCheck size={14}/></h4><dl className="properties"><div><dt>Geometry revision</dt><dd>{s.revision}</dd></div><div><dt>Unit system</dt><dd>millimeters</dd></div></dl><Note>Dimensions and volume are measured from the built CAD geometry.</Note>
    </> : <Empty icon={<MousePointer2 size={24}/>} title="No component selected">Select geometry in the canvas or a component in Explorer to inspect its measured properties.</Empty>;
    if (panel === 'review') return <>
      <div className="review-stats"><div className="positive"><b>{passed}</b><span>Passed</span></div><div className="negative"><b>{failed}</b><span>Failed</span></div><div className="warning-text"><b>{unknown}</b><span>Unverified</span></div></div>
      <p className="description">{s.report ? `${s.reportRevision} · ${rows.length} recorded requirements. ${s.report.ready_for_review ? 'Ready for review.' : 'Requirements need attention.'}` : 'Build a design to collect engineering evidence.'}</p>
      {s.reportRevision !== s.revision && s.revision && <Note warning>Evidence is for {s.reportRevision}. The canvas retains geometry from {s.revision}.</Note>}
      <div className="filter-tabs">{['all', 'attention'].map(value => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{value === 'all' ? `All checks · ${rows.length}` : `Needs attention · ${failed + unknown}`}</button>)}</div>
      <div className="check-list">{rows.filter(row => filter === 'all' || row.status !== 'pass').map(row => <details key={row.id} className={`check-entry ${row.status}`}><summary>{row.status === 'pass' ? <CheckCircle2 size={15}/> : <AlertCircle size={15}/>}<span>{row.description}</span><small>{row.status}</small><ChevronDown size={12}/></summary><div className="check-detail"><span className="requirement-id">{row.id} · {row.mandatory ? 'Required' : 'Informational'}</span>{row.result && <dl><div><dt>Measured</dt><dd>{JSON.stringify(row.result.actual)} {row.result.unit}</dd></div><div><dt>Required</dt><dd>{JSON.stringify(row.result.expected)}</dd></div></dl>}<p>{row.reason}</p></div></details>)}</div>
      {filter === 'attention' && !failed && !unknown && <Note>No checks need attention.</Note>}
      {s.report?.blocking_reasons.map((text, index) => <Note warning key={index}>{text}</Note>)}
      {s.report?.errors.map((text, index) => <p className="negative" key={index}>{text}</p>)}
      {!!s.report?.assumptions.length && <details className="assumptions"><summary>Design assumptions</summary>{s.report.assumptions.map((item, index) => <p key={index}>{item.description}</p>)}</details>}
      <Note warning>CAD evidence is not physical validation. Fit, material behavior, and manufacturing performance remain unverified.</Note>
    </>;
    if (panel === 'history') return <>
      <p className="description">Every attempt is preserved. Choosing a revision changes the preview, without changing its source.</p>
      {s.design?.revisions.length ? [...s.design.revisions].reverse().map(row => <button className={`revision-card ${s.revision === row.id ? 'active' : ''}`} disabled={!row.scene || s.busy} onClick={() => void s.run(() => s.showRevision(row.id))} key={row.id}><History size={15}/><span className="revision-copy"><strong>{row.id}<small>{row.id === s.design?.latest_revision ? 'LATEST' : titleCase(row.status)}</small></strong><span>{row.summary || titleCase(row.status)}</span><small>{row.checks !== undefined ? `${row.checks}/${row.requirements} checks` : 'No geometry'}{row.elapsed_seconds !== undefined ? ` · ${row.elapsed_seconds.toFixed(1)}s` : ''}</small></span></button>) : <Empty icon={<History size={24}/>} title="A history of your design">Revisions will appear here after your first build.</Empty>}
      {s.historical && <button className="soft-action full" onClick={() => void s.run(() => s.showRevision(s.design!.display_revision!))}><RotateCcw size={14}/>Return to current revision</button>}
    </>;
    if (panel === 'compare') return s.data?.comparison ? <>
      <p className="description">Component geometry and requirement changes against the previous built revision.</p><div className="compare-pair"><span>{s.data.comparison.baseline}</span><ChevronRight size={14}/><strong>{s.revision}</strong></div>
      <button role="switch" aria-checked={s.overlay} className="setting-row" onClick={() => s.setOverlay(!s.overlay)}><span><strong>Previous geometry overlay</strong><small>Changed prior components appear in amber.</small></span><span className={`switch ${s.overlay ? 'on' : ''}`}/></button>
      <h4>Geometry changes <Columns2 size={14}/></h4><dl className="properties">{Object.entries({ Modified: Object.keys(s.data.comparison.components.changed), Added: s.data.comparison.components.added, Removed: s.data.comparison.components.removed }).map(([label, ids]) => <div key={label}><dt>{label}</dt><dd>{ids.length ? ids.join(', ') : 'None'}</dd></div>)}</dl>
      <h4>Requirement changes <CheckCircle2 size={14}/></h4><dl className="properties">{Object.entries({ Modified: Object.keys(s.data.comparison.requirements.modified), Added: s.data.comparison.requirements.added, Removed: s.data.comparison.requirements.removed }).map(([label, ids]) => <div key={label}><dt>{label}</dt><dd>{ids.length ? ids.join(', ') : 'None'}</dd></div>)}</dl><Note>Overlay compares recorded geometry identities. It is not an exact solid difference.</Note>
    </> : <Empty icon={<Columns2 size={24}/>} title="Room to compare">Build a second revision to compare its actual geometry and requirements with the earlier result.</Empty>;
    if (panel === 'source') return sourceFiles.length ? <>
      <p className="description">{s.revision} · Python and manifest files from this retained revision.</p><label className="field-label" htmlFor="source-file">Source file</label><select id="source-file" value={sourceFile} onChange={event => setSourceFile(event.target.value)}>{sourceFiles.map(file => <option key={file} value={file}>{file.replace(/^project\//, '')}</option>)}</select>
      <div className="source-toolbar"><span><Code2 size={13}/>{sourceFile.split('/').pop()}</span><a href={s.fileUrl(sourceFile)} download aria-label="Download source file"><Download size={14}/></a></div><pre className="source-code" tabIndex={0} aria-label="Source code">{sourceError || sourceText || 'Loading source…'}</pre>
      <Note>Retained revisions are read-only. Ask your assistant to make changes in a new revision.</Note>
    </> : <Empty icon={<FileCode2 size={24}/>} title="Source stays yours">Build a design to inspect its Python source and manifest here.</Empty>;
    if (panel === 'activity') return <>
      <div className="tag-row"><span className="tag blue"><Sparkles size={12}/>{s.mcpMode ? 'IDE assistant · MCP' : 'Codex CLI'}</span>{s.selected && <button className="tag" onClick={() => pick(null)} title="Clear selection"><Box size={12}/>{s.selected}<X size={12}/></button>}</div>
      {!s.design?.messages.length && <Empty icon={<Sparkles size={24}/>} title={s.mcpMode ? 'Design from your IDE' : 'What are we making?'}>{s.mcpMode ? 'Describe a part to your IDE assistant. Designs, explanations, and measured feedback appear here through MCP.' : 'Describe the geometry, dimensions, and what the part needs to fit.'}</Empty>}
      <div className="conversation">{s.design?.messages.map((message, index) => <article className={`message ${message.role}`} key={index}><header><span>{message.role === 'assistant' ? <Sparkles size={12}/> : <MousePointer2 size={12}/>}{message.role === 'assistant' ? 'Designer' : 'You'}{message.revision && <code>{message.revision}</code>}</span><time>{new Date(message.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time></header><p>{message.text}</p>{message.questions?.map(question => <p key={question} className="question">{question}</p>)}</article>)}{s.busy && <div className="working"><LoaderCircle size={14} className="spin"/>{s.progress || 'Working…'}</div>}<div ref={bottom}/></div>
    </>;
    if (panel === 'settings') return <>
      <p className="description">Display preferences stay in this browser. Your source and engineering evidence stay unchanged.</p><h4>Appearance <Sun size={14}/></h4><div className="theme-options" aria-label="Color theme">{(['light', 'dark', 'system'] as Theme[]).map(value => <button key={value} className={preferences.theme === value ? 'active' : ''} aria-pressed={preferences.theme === value} onClick={() => setPreference('theme', value)}>{titleCase(value)}</button>)}</div>
      <h4>Viewport <SlidersHorizontal size={14}/></h4>{([
        ['grid', 'Construction grid', 'An XY reference plane beneath your geometry.'], ['axes', 'Coordinate axes', 'Show the model axes and coordinate-frame controls.'], ['edges', 'Component edges', 'Draw the edges of the built geometry.'], ['ghost', 'Ghost reference envelopes', 'Keep reference parts transparent.'],
      ] as const).map(([key, label, description]) => <button className="setting-row" role="switch" aria-checked={preferences[key]} onClick={() => setPreference(key, !preferences[key])} key={key}><span><strong>{label}</strong><small>{description}</small></span><span className={`switch ${preferences[key] ? 'on' : ''}`}/></button>)}
      <h4>Keyboard shortcuts</h4><dl className="properties">{commands.filter(command => command.key).map(command => <div key={command.name}><dt>{command.name}</dt><dd><kbd>{command.key}</kbd></dd></div>)}<div><dt>Command palette</dt><dd><kbd>Ctrl / ⌘ K</kbd></dd></div></dl>
    </>;
    if (panel === 'session') return <>
      <span className={`tag ${s.session?.authorized ? 'green' : ''}`}><span className={`dot ${s.session?.authorized ? '' : 'off'}`}/>{s.session?.authorized ? 'Trusted local session' : 'Session locked'}</span><h4>Connection <ShieldCheck size={14}/></h4><dl className="properties"><div><dt>Designer</dt><dd>{s.mcpMode ? 'IDE assistant via MCP' : 'Codex CLI'}</dd></div><div><dt>Workspace</dt><dd className="workspace-path">{s.session?.workspace || 'Connecting…'}</dd></div><div><dt>Active job</dt><dd>{s.busy ? titleCase(s.job!.status) : 'None'}</dd></div></dl>
      <Note>Python executes locally under your account, without sandboxing. Enable a session only for source and dependencies you trust.</Note><p className="description">{s.mcpMode ? 'Continue your conversation in the IDE. Studio makes no separate model calls.' : 'This optional mode uses your signed-in Codex CLI.'}</p>
      <button className="primary-action full" disabled={!s.session} onClick={() => void s.run(() => s.authorize(!s.session?.authorized))}>{s.session?.authorized ? 'Lock session' : 'Enable session'}</button>
    </>;
  }
  function panelFooter() {
    if (panel === 'properties' && s.selected) return <button className="soft-action full" onClick={() => pick(null)}><X size={14}/>Clear selection</button>;
    if (panel === 'review' && s.report) return <a className="soft-action full" href={s.fileUrl('run.json', s.reportRevision)} download><Download size={14}/>Download evidence report</a>;
    if (panel === 'history') return <button className="soft-action full" disabled={!canRebuild} onClick={() => void s.run(s.rebuild)}><RotateCcw size={14}/>Rebuild current source</button>;
    if (panel === 'source' && sourceFiles.length) return <a className="soft-action full" href={sourceBundle} download><Download size={14}/>Download source bundle</a>;
    if (panel === 'activity') return s.mcpMode ? <div className="mcp-composer"><strong>Continue in your IDE</strong><p>Your assistant sends source and repairs through MCP. Studio builds and measures them locally.</p>{s.busy && <button className="soft-action full" onClick={() => void s.run(s.cancel)}><Square size={12}/>Cancel build</button>}</div> : <form className="composer" onSubmit={event => { event.preventDefault(); void s.run(async () => { await s.submit(prompt); setPrompt(''); }); }}><textarea aria-label="Describe your design" placeholder={s.historical ? 'Return to the current revision to continue' : 'Describe a part or a change…'} value={prompt} disabled={s.busy || s.historical || !s.session?.authorized} onChange={event => setPrompt(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }}/><div><span>{s.session?.model}</span>{s.busy ? <button type="button" aria-label="Cancel job" onClick={() => void s.run(s.cancel)}><Square size={14}/></button> : <button type="submit" className="primary-action" aria-label="Send design request" disabled={!prompt.trim() || s.historical || !s.session?.authorized}><ArrowUp size={15}/></button>}</div></form>;
    return null;
  }

  return <div className={`app ${focusMode ? 'focus-mode' : ''}`}>
    <header className="topbar"><nav className="breadcrumb" aria-label="Design location"><span>Workspace</span><i>/</i><strong>{s.design?.title || 'Untitled design'}</strong><i>/</i><code>{s.revision || 'Draft'}</code></nav><div className="top-right">
      <button className="session-chip" aria-label="Session status" onClick={() => openPanel('session')}><span className={`dot ${s.session?.authorized ? '' : 'off'}`}/>{s.session ? s.session.authorized ? `Local · ${s.mcpMode ? 'MCP' : 'Codex'}` : 'Session locked' : 'Connecting…'}</button><span className="divider"/>
      <IconButton label="Command palette" onClick={() => { setCommandQuery(''); setModal('commands'); }}><Search size={17}/></IconButton><IconButton label="Agent activity" active={panel === 'activity'} onClick={() => openPanel('activity')}><Activity size={17}/></IconButton><IconButton label="Toggle light and dark theme" onClick={() => setPreference('theme', theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={17}/> : <Moon size={17}/>}</IconButton><IconButton label="Settings" active={panel === 'settings'} onClick={() => openPanel('settings')}><Settings2 size={17}/></IconButton>
      <button className="export-button" aria-label="Export design" aria-expanded={menu === 'export'} onClick={() => toggleMenu('export')}><Download size={15}/><span>Export</span><ChevronDown size={12}/></button>
    </div></header>
    <main className={`workarea ${panel ? 'has-panel' : ''} ${explorer ? 'has-explorer' : ''}`} aria-label="CAD workspace">
      <div className="canvas"><Viewer scene={scene} previous={s.previous?.scene || null} selected={s.selected} hidden={s.hidden} isolated={s.isolated} overlay={s.overlay} ghost={preferences.ghost} onSelect={pick} controls={controls} theme={theme} grid={preferences.grid} axes={preferences.axes} edges={preferences.edges}/></div>
      <div className="viewport-context"><span/>DESIGN VIEW <i>/</i>{views.find(item => item[0] === view)?.[1].toUpperCase()}{s.overlay && <em>AMBER · PREVIOUS GEOMETRY</em>}</div>
      {!focusMode && (explorer ? <aside className="explorer floating" aria-label="Project explorer"><header className="explorer-head"><strong><PanelLeft size={15}/>Explorer</strong><div><IconButton label="Search explorer" active={searchExplorer} onClick={() => { setSearchExplorer(!searchExplorer); setQuery(''); }}><Search size={14}/></IconButton><IconButton label="Open saved workflows" onClick={openLibrary}><FolderOpen size={14}/></IconButton><IconButton label="Collapse explorer" onClick={() => setExplorer(false)}><PanelLeftClose size={14}/></IconButton></div></header>
        <div className="explorer-body">{searchExplorer && <label className="explorer-find"><Search size={14}/><input autoFocus placeholder="Filter workspace…" aria-label="Filter workspace" value={query} onChange={event => setQuery(event.target.value)}/></label>}
          <Section title="Designs" count={s.designs.length}>{s.designs.filter(item => item.title.toLowerCase().includes(query.toLowerCase())).map(item => <button className={`tree-row ${item.id === s.design?.id ? 'selected' : ''}`} disabled={s.busy && item.id !== s.design?.id} key={item.id} onClick={() => void s.run(() => s.openDesign(item))}><Box size={14}/><span>{item.title}</span><i className={`row-state ${item.status}`} title={titleCase(item.status)}/></button>)}{!s.designs.length && <p className="no-rows">Your designs will appear here.</p>}</Section>
          <button className="new-project" disabled={s.busy} onClick={newDesign}><Plus size={14}/>New design</button>
          <Section title="Components" count={scene?.components.length || 0}>{scene?.components.filter(item => item.id.toLowerCase().includes(query.toLowerCase())).map(item => <div className={`component-row ${s.hidden.has(item.id) || (s.isolated && s.isolated !== item.id) ? 'muted-row' : ''}`} key={item.id}><button className={`tree-row ${s.selected === item.id ? 'selected' : ''}`} onClick={() => pick(s.selected === item.id ? null : item.id)}>{item.role === 'reference-envelope' ? <Boxes size={14}/> : <Box size={14}/>}<span>{item.id}</span></button><IconButton label={`${s.hidden.has(item.id) ? 'Show' : 'Hide'} ${item.id}`} onClick={() => s.toggleHidden(item.id)}>{s.hidden.has(item.id) ? <EyeOff size={14}/> : <Eye size={14}/>}</IconButton></div>)}{!scene && <p className="no-rows">No built geometry yet.</p>}</Section>
          <Section title="Source files" count={sourceFiles.length} open={false}>{sourceFiles.filter(file => file.toLowerCase().includes(query.toLowerCase())).map(file => <button className={`tree-row ${sourceFile === file && panel === 'source' ? 'selected' : ''}`} key={file} onClick={() => { setSourceFile(file); openPanel('source'); }}><FileCode2 size={14}/><span className="mono">{file.replace(/^project\//, '')}</span></button>)}{!sourceFiles.length && <p className="no-rows">Source appears after a build.</p>}</Section>
          <Section title="Revisions" count={s.design?.revisions.length || 0} open={false}>{s.design?.revisions.map(row => <button key={row.id} className={`tree-row ${row.id === s.revision ? 'selected' : ''}`} disabled={!row.scene || s.busy} onClick={() => void s.run(() => s.showRevision(row.id))}><History size={14}/><span className="mono">{row.id}{row.id === s.design?.latest_revision ? ' · Current' : ''}</span><i className={`row-state ${row.status}`}/></button>)}{!s.design?.revisions.length && <p className="no-rows">Every attempt, preserved.</p>}</Section>
        </div><footer className="explorer-foot"><span><span className="dot"/>Local workspace</span><span>{s.mcpMode ? 'MCP WORKFLOW' : 'CODEX CLI'}</span></footer>
      </aside> : <button className="explorer-toggle floating" aria-label="Show explorer" onClick={() => setExplorer(true)}><PanelLeft size={18}/></button>)}
      {!focusMode && <button className="review-trigger floating" aria-label="Open engineering checks" onClick={() => openPanel('review')}>{s.report?.ready_for_review ? <CheckCircle2 className="positive" size={15}/> : <Info className={failed ? 'negative' : ''} size={15}/>}<strong>{s.report ? `${passed} / ${rows.length} checks` : 'No checks yet'}</strong><span>{s.report ? s.report.ready_for_review ? unknown ? `${unknown} unverified` : 'Ready for review' : 'Needs attention' : 'Not evaluated'}</span><ChevronRight size={13}/></button>}
      {!scene && !s.busy && <div className="empty-stage"><span className="empty-stage-icon"><Box size={30} strokeWidth={1}/></span><span className="eyebrow">From intent to geometry</span><h1>{s.design ? 'Your design is taking shape.' : 'A place for your next part.'}</h1><p>{s.design ? 'Continue with your assistant, or inspect the latest build evidence.' : s.mcpMode ? 'Design in your IDE. See it, measure it, and refine it here.' : 'Describe a part, then build, measure, and refine it here.'}</p><button className="soft-action" onClick={s.design ? () => openPanel('review') : newDesign}>{s.design ? <CheckCircle2 size={14}/> : <Plus size={14}/>} {s.design ? 'Review evidence' : 'Start a design'}<ChevronRight size={13}/></button></div>}
      {!focusMode && panel && <Pane title={panelInfo[panel][1]} eyebrow={panelInfo[panel][0]} onClose={() => setPanel(null)} footer={panelFooter()}>{panelContent()}</Pane>}
      {s.historical && !focusMode && <div className="historical-banner"><History size={14}/>Viewing {s.revision}<button onClick={() => void s.run(() => s.showRevision(s.design!.display_revision!))}>Return to current</button></div>}
      {s.busy && <div className="job-toast floating" role="status"><LoaderCircle className="spin" size={16}/><span>{s.progress || 'Preparing design…'}</span>{!s.downloading && <button onClick={() => void s.run(s.cancel)} aria-label="Cancel job" title="Cancel job"><Square size={12}/></button>}</div>}
      {needsAttention && !focusMode && <button className="attention-toast" onClick={() => openPanel('review')}><AlertCircle size={14}/>{titleCase(s.design!.status)}{s.revision ? ` · Showing ${s.revision}` : ''}<ChevronRight size={13}/></button>}
      {!s.session?.authorized && s.session && !focusMode && <div className="authorization-note floating"><ShieldCheck size={16}/><span>Enable a trusted local session to build Python.</span><button onClick={() => void s.run(() => s.authorize(true))}>Enable session<ChevronRight size={12}/></button></div>}
      {!focusMode && <div className="bottom-left"><button className="revision-button floating" onClick={() => openPanel('history')}><History size={14}/><strong>{s.revision || 'Draft'}</strong><span>{s.historical ? 'Historical revision' : 'Current revision'}</span><ChevronDown size={12}/></button><small><Info size={12}/>Physical fit unverified</small></div>}
      <nav className="dock floating" aria-label="Viewport controls">{focusMode ? <button onClick={() => setFocusMode(false)}><Expand size={16}/>Restore workspace</button> : <>
        <button onClick={resetCamera} title="Fit model · F" aria-label="Fit model"><Focus size={16}/><span>Fit</span></button><i/>
        <button className={menu === 'view' ? 'active' : ''} onClick={() => toggleMenu('view')} aria-expanded={menu === 'view'}><Box size={16}/><span>View</span><ChevronDown size={12}/></button><i/>
        <button className={menu === 'inspect' ? 'active' : ''} onClick={() => toggleMenu('inspect')} aria-expanded={menu === 'inspect'}><SlidersHorizontal size={16}/><span>Inspect</span><ChevronDown size={12}/></button><i/>
        <button className={panel === 'compare' ? 'active' : ''} onClick={() => openPanel('compare')} title="Compare revisions · C"><Columns2 size={16}/><span>Compare</span></button><i/>
        <button aria-label="Distraction-free mode" title="Distraction-free mode · D" onClick={() => { setFocusMode(true); setMenu(null); }}><Expand size={16}/></button>
      </>}</nav>
      {preferences.axes && !focusMode && <div className="orientation" aria-label="Coordinate frame, Z up"><div><button className="axis-z" aria-label="View from Z axis" onClick={() => changeView('top')}>Z</button><button className="axis-y" aria-label="View from Y axis" onClick={() => changeView('front')}>Y</button><span/><button className="axis-x" aria-label="View from X axis" onClick={() => changeView('right')}>X</button></div><small>MM · Z UP</small></div>}
      {menu && !focusMode && <><button className="menu-dismiss" aria-label="Dismiss menu" onClick={() => setMenu(null)}/><div className={`popup-menu floating ${menu}`} aria-label={`${titleCase(menu)} options`}>
        {menu === 'view' && <><span className="eyebrow">Standard views</span>{views.map(([id, title]) => <button key={id} className={view === id ? 'active' : ''} onClick={() => changeView(id)}><Box size={14}/><span>{title}</span>{view === id && <Check size={14}/>}</button>)}<hr/><button onClick={resetCamera}><RotateCcw size={14}/>Reset camera</button></>}
        {menu === 'inspect' && <><span className="eyebrow">Inspection tools</span><button onClick={() => openPanel('properties')}><MousePointer2 size={14}/>Component properties<kbd>I</kbd></button><button onClick={() => openPanel('review')}><CheckCircle2 size={14}/>Engineering checks<kbd>R</kbd></button><button onClick={() => openPanel('history')}><History size={14}/>Revision history<kbd>H</kbd></button><button onClick={() => openPanel('source')}><FileCode2 size={14}/>Source files</button><hr/><button onClick={() => openPanel('settings')}><Settings2 size={14}/>Viewport preferences</button></>}
        {menu === 'export' && <><span className="eyebrow">Export design</span><button disabled={!canExport} onClick={() => { setMenu(null); void s.run(() => s.exportModel('step', () => setMenu('export'))); }}><Box size={14}/><span>STEP geometry</span><small>.step</small></button><button disabled={!canExport} onClick={() => { setMenu(null); void s.run(() => s.exportModel('stl', () => setMenu('export'))); }}><Layers2 size={14}/><span>STL mesh</span><small>.stl</small></button><p className="menu-note">Downloads start automatically. Multiple parts arrive together in a ZIP.</p><hr/>{s.data ? <><a href={sourceBundle} download><FileCode2 size={14}/><span>Source bundle</span><small>.zip</small></a><a href={s.fileUrl('run.json', s.reportRevision)} download><ArrowDownToLine size={14}/><span>Evidence report</span><small>.json</small></a></> : <p className="menu-note">Build a design to download its source and evidence.</p>}{!canExport && <p className="menu-note">Geometry export requires the latest passing CAD evidence and an enabled session.</p>}{!!exports.length && <><hr/><span className="eyebrow">Ready to download</span>{exports.map(file => <a href={s.fileUrl(file)} download key={file}><Download size={14}/><span>{file.split('/').pop()}</span></a>)}</>}</>}
      </div></>}
    </main>
    {s.error && <div className="error-toast" role="alert"><AlertCircle size={16}/><span>{s.error}</span>{canRebuild && /workflow evaluator changed|saved evidence is stale/.test(s.error) && <button className="soft-action" onClick={() => void s.run(s.rebuild)}>Rebuild current source</button>}<IconButton label="Dismiss error" onClick={() => s.setError('')}><X size={15}/></IconButton></div>}
    {modal && <Modal title={modal === 'commands' ? 'Command palette' : modal === 'library' ? 'Saved workflows' : 'Create a design'} onClose={() => setModal(null)} className={modal === 'commands' ? 'command-modal' : ''}>
      {modal === 'commands' ? <><label className="command-search"><Search size={18}/><input autoFocus placeholder="Search commands and tools…" aria-label="Search commands" value={commandQuery} onChange={event => setCommandQuery(event.target.value)}/><kbd>ESC</kbd></label><div className="command-list">{commands.filter(command => command.name.toLowerCase().includes(commandQuery.toLowerCase())).map(command => <button key={command.name} onClick={() => { setModal(null); command.action(); }}>{command.icon}<span>{command.name}</span>{command.key && <kbd>{command.key}</kbd>}</button>)}</div><footer className="command-foot">Choose a workspace action<span>STUDIO COMMANDS</span></footer></> : <div className="modal-content">
        {modal === 'new' ? <><p>{s.mcpMode ? 'Describe a part to your IDE assistant, or start with a local example. Your assistant receives the selected design through MCP.' : 'Start with a local example, or open Agent activity to describe a new design.'}</p><button className="primary-action full" disabled={s.busy} onClick={() => { if (!s.mcpMode) s.startDraft(); setModal(null); openPanel('activity'); }}><Sparkles size={15}/>{s.mcpMode ? 'Continue with your IDE assistant' : 'Open design assistant'}</button><span className="eyebrow modal-label">Source-backed examples</span>{[['square-mount', 'Mounting plate', 'Four mounting holes and reference envelopes'], ['enclosure', 'Electronics enclosure', 'A base, lid, and measured skirt clearance'], ['flange', 'Pipe flange', 'A concentric bore and six-hole pattern']].map(([id, title, description]) => <button className="library-row" key={id} disabled={!s.session?.authorized || s.busy} onClick={() => startExample(id)}><Box size={20}/><span><strong>{title}</strong><small>{description}</small></span><ChevronRight size={16}/></button>)}{!s.session?.authorized && <button className="soft-action full" onClick={() => void s.run(() => s.authorize(true))}><ShieldCheck size={14}/>Enable session for examples</button>}</> : <><p>Open a local copy in Studio. Original source and evidence stay intact.</p>{saved.length ? saved.map(item => <button className="library-row" key={item.id} disabled={s.busy || !s.session?.authorized} onClick={() => void s.run(async () => { await s.create(undefined, item.id); setModal(null); })}><FolderOpen size={18}/><span><strong>{item.title}</strong><small>{titleCase(item.outcome || 'Not evaluated')}</small></span><ChevronRight size={16}/></button>) : <Empty icon={<FolderOpen size={24}/>} title="No saved workflows">Manual workflow runs within this session's trusted root appear here.</Empty>}</>}
      </div>}
    </Modal>}
  </div>;
}

createRoot(document.getElementById('root')!).render(<App/>);
