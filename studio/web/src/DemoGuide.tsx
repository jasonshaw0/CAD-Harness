export type DemoInfo = {
  design_id: string;
  failed_revision: string;
  repaired_revision: string;
};

export function DemoGuide({ demo, revision, busy, onFailure, onRepair, onChecks, onCompare, onSource, onExport }: {
  demo: DemoInfo; revision: string | null; busy: boolean;
  onFailure: () => void; onRepair: () => void; onChecks: () => void;
  onCompare: () => void; onSource: () => void; onExport: () => void;
}) {
  return <div className="demo-guide">
    <h3>Inspect a failure and its repair</h3>
    <p className="description">Two revisions were built locally from bundled Python and measured by the CAD evaluator. No assistant or model was used.</p>
    <button className="demo-step" aria-pressed={revision === demo.failed_revision} disabled={busy} onClick={onFailure}>
      <span className="demo-number">1</span><span><strong>Inspect the missing hole</strong><small>{demo.failed_revision} · Three holes, where four are required.</small></span>
    </button>
    <p className="description">Open the checks and expand <strong>holes count</strong>. The count comes from the built geometry.</p>
    <button className="soft-action full" onClick={onChecks}>Open measured checks</button>
    <button className="demo-step" aria-pressed={revision === demo.repaired_revision} disabled={busy} onClick={onRepair}>
      <span className="demo-number">2</span><span><strong>Inspect the repaired plate</strong><small>{demo.repaired_revision} · Four holes; the frozen brief is unchanged.</small></span>
    </button>
    <p className="description">The repair changes the manifest's selected variant. Both revisions retain editable Python, the manifest, and their measured evidence.</p>
    <div className="demo-actions">
      <button className="soft-action full" disabled={busy} onClick={onCompare}>Compare the revisions</button>
      <button className="soft-action full" onClick={onSource}>Inspect editable source</button>
      <button className="soft-action full" disabled={busy} onClick={onExport}>Export repaired part…</button>
    </div>
    <p className="description">To export STEP or STL, enable a trusted session and choose a format. Export rechecks the latest evidence and includes only the printable plate.</p>
    <p className="description">Select the plate in Explorer to inspect or isolate it. Drag the canvas to orbit, or choose a standard view below.</p>
    <p className="demo-limit">Illustrative dimensions only. Physical fit, material behavior, and manufacturing performance remain unverified.</p>
  </div>;
}
