import React from 'react';
import { AlertCircle, CheckCircle2, Info } from 'lucide-react';
import { cn } from '../../lib/utils';

export type NoticeTone = 'error' | 'success' | 'info' | 'warning';

const TONE_CLASSES: Record<NoticeTone, string> = {
  error: 'bg-rose-950/40 border-rose-500/35 text-rose-200',
  success: 'bg-emerald-950/35 border-emerald-500/35 text-emerald-200',
  info: 'bg-sky-950/35 border-sky-500/35 text-sky-200',
  warning: 'bg-amber-950/35 border-amber-500/35 text-amber-200',
};

export interface NoticeProps {
  tone?: NoticeTone;
  children: React.ReactNode;
  className?: string;
}

/** Compact inline feedback banner for errors, confirmations, and completions. */
export const Notice: React.FC<NoticeProps> = ({ tone = 'info', children, className }) => {
  const Icon =
    tone === 'error' || tone === 'warning'
      ? AlertCircle
      : tone === 'success'
      ? CheckCircle2
      : Info;
  const iconColor =
    tone === 'error'
      ? 'text-rose-400'
      : tone === 'warning'
      ? 'text-amber-400'
      : tone === 'success'
      ? 'text-emerald-400'
      : 'text-sky-400';

  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'px-3 py-2 rounded-md border text-[13px] flex items-start gap-2 leading-snug',
        TONE_CLASSES[tone],
        className
      )}
    >
      <Icon className={cn('size-4 shrink-0 mt-0.5', iconColor)} aria-hidden="true" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
};
