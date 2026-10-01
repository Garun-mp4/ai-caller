'use client';

import type { ReactNode } from 'react';
import Dialog from '@/components/Dialog';

export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Подтвердить',
  busy = false,
  danger = false,
  children,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  busy?: boolean;
  danger?: boolean;
  children?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return <Dialog title={title} description={description} onClose={onCancel} dismissible={!busy}>
    {children}
    <div className="modal-actions">
      <button type="button" className="btn" onClick={onCancel} disabled={busy}>Отмена</button>
      <button type="button" className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm} disabled={busy}>{busy ? 'Выполняем…' : confirmLabel}</button>
    </div>
  </Dialog>;
}
