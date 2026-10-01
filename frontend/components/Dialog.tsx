'use client';

import { useEffect, useId, useRef, type ReactNode } from 'react';

export default function Dialog({
  title,
  description,
  children,
  onClose,
  dismissible = true,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  dismissible?: boolean;
}) {
  const dialog = useRef<HTMLElement>(null);
  const closeRef = useRef(onClose);
  const ids = useId();
  useEffect(() => { closeRef.current = onClose; }, [onClose]);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const firstTarget = dialog.current?.querySelector<HTMLElement>('[data-autofocus], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]');
    firstTarget?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && dismissible) {
        event.preventDefault(); closeRef.current(); return;
      }
      if (event.key !== 'Tab' || !dialog.current) return;
      const targets = Array.from(dialog.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'));
      if (!targets.length) { event.preventDefault(); return; }
      const first = targets[0];
      const last = targets[targets.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialog.current.contains(active))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (active === last || !dialog.current.contains(active))) { event.preventDefault(); first.focus(); }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [dismissible]);

  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && dismissible) closeRef.current(); }}>
    <section ref={dialog} className="modal" role="dialog" aria-modal="true" aria-labelledby={`dialog-title-${ids}`} aria-describedby={description ? `dialog-description-${ids}` : undefined} tabIndex={-1}>
      <h2 className="modal-title" id={`dialog-title-${ids}`}>{title}</h2>
      {description && <p className="modal-copy" id={`dialog-description-${ids}`}>{description}</p>}
      {children}
    </section>
  </div>;
}
