import React from 'react';
import { cn } from '../../lib/utils';

export interface EmptyCanvasProps {
  label: string;
  meta?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionIcon?: React.ReactNode;
  className?: string;
}

/** Precision instrument empty state with subtle dot-matrix canvas and minimal geometry. */
export const EmptyCanvas: React.FC<EmptyCanvasProps> = ({
  label,
  meta,
  actionLabel,
  onAction,
  actionIcon,
  className,
}) => {
  return (
    <div
      className={cn(
        'dot-grid-canvas rounded-md bg-[#08090c] border border-[#1d2028] flex flex-col items-center justify-center text-center p-6 select-none',
        className
      )}
    >
      <div className="w-9 h-9 rounded-md bg-[#12151b] border border-[#242833] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)] flex items-center justify-center mb-3">
        <svg viewBox="0 0 20 20" className="w-4 h-4 text-[#5d6473]" aria-hidden="true">
          <path
            d="M2 14 L6 14 L8.5 5 L11.5 14 L14.5 9.5 L18 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="8.5" cy="5" r="1.2" fill="#38bdf8" />
        </svg>
      </div>
      <div className="text-[12px] font-medium text-[#98a0ae] tracking-wide">{label}</div>
      {meta && (
        <div className="mt-1 text-[11px] font-mono text-[#5d6473] tabular-nums">{meta}</div>
      )}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-3.5 h-7 px-3 rounded-md bg-[#161920] hover:bg-[#1e222b] border border-[#2b303c] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)] text-[11px] font-medium text-[#eef0f4] inline-flex items-center gap-1.5 transition-colors"
        >
          {actionIcon}
          <span>{actionLabel}</span>
        </button>
      )}
    </div>
  );
};
