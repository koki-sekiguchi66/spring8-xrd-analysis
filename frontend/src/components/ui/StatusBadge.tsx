import React from 'react';
import { cn } from '../../lib/utils';

export type BadgeTone = 'neutral' | 'sky' | 'amber' | 'emerald' | 'rose';

const BADGE_STYLES: Record<BadgeTone, string> = {
  neutral: 'bg-[#1c1f26] text-[#9ca3b0] border-[#2a2e38]',
  sky: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
  amber: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  emerald: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  rose: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
};

const DOT_STYLES: Record<BadgeTone, string> = {
  neutral: 'bg-[#636b78]',
  sky: 'bg-sky-400',
  amber: 'bg-amber-400',
  emerald: 'bg-emerald-400',
  rose: 'bg-rose-400',
};

export interface StatusBadgeProps {
  tone?: BadgeTone;
  dot?: boolean;
  mono?: boolean;
  children: React.ReactNode;
  className?: string;
}

/** Single-line non-wrapping status indicator tag. */
export const StatusBadge: React.FC<StatusBadgeProps> = ({
  tone = 'neutral',
  dot = false,
  mono = false,
  children,
  className,
}) => {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 h-5 px-2 rounded border text-[11px] font-medium whitespace-nowrap shrink-0 tabular-nums',
        BADGE_STYLES[tone],
        mono && 'font-mono',
        className
      )}
    >
      {dot && <span className={cn('size-1.5 rounded-full shrink-0', DOT_STYLES[tone])} />}
      <span>{children}</span>
    </span>
  );
};
