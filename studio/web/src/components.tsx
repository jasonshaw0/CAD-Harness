import { useEffect, useRef, type ReactNode } from 'react';
import { X, ChevronDown, Info } from 'lucide-react';

export function IconButton({ label, children, active = false, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; active?: boolean }) {
  return <button {...props} type="button" className={`icon-button ${active ? 'active' : ''} ${props.className || ''}`} aria-label={label} title={label}>{children}</button>;
}
export function Section({ title, count, children, open = true }: { title: string; count: number; children: ReactNode; open?: boolean }) {
  return <details className="tree-section" open={open}><summary><ChevronDown size={12}/><span>{title}</span><small>{String(count).padStart(2, '0')}</small></summary><div className="tree-content">{children}</div></details>;
}
export function Note({ children, warning = false }: { children: ReactNode; warning?: boolean }) {
  return <div className={`inline-note ${warning ? 'warning' : ''}`}><Info size={14}/><span>{children}</span></div>;
}
export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return <div className="empty-pane"><span className="empty-icon">{icon}</span><strong>{title}</strong><p>{children}</p></div>;
}
export function Pane({ title, eyebrow, onClose, children, footer }: { title: string; eyebrow: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  return <aside className="detail-panel floating" aria-label={title}>
    <header className="pane-header"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div><IconButton label="Close panel" onClick={onClose}><X size={16}/></IconButton></header>
    <div className="pane-scroll">{children}</div>{footer && <footer className="pane-bottom">{footer}</footer>}
  </aside>;
}
export function Modal({ title, onClose, children, className = '' }: { title: string; onClose: () => void; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className={`modal ${className}`} aria-label={title} onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <header className="modal-head"><h2>{title}</h2><IconButton label="Close dialog" onClick={onClose}><X size={16}/></IconButton></header>{children}
  </dialog>;
}
