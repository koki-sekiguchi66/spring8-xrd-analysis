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
      <div className="w-11 h-11 rounded-lg bg-[#12151b] border border-[#272c38] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)] flex items-center justify-center mb-3.5">
        <svg viewBox="0 0 20 20" className="w-5 h-5 text-[#7c8494]" aria-hidden="true">
          <path
            d="M2 14 L6 14 L8.5 5 L11.5 14 L14.5 9.5 L18 14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="8.5" cy="5" r="1.4" fill="#38bdf8" />
        </svg>
      </div>
      <div className="text-[13px] font-medium text-[#cfd4de] tracking-wide">{label}</div>
      {meta && (
        <div className="mt-1 text-[12px] font-mono text-[#7c8494] tabular-nums">{meta}</div>
      )}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-4 h-9 px-4 rounded-md bg-gradient-to-b from-[#1e232d] to-[#171b22] hover:from-[#262c38] hover:to-[#1e232d] border border-[#303645] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)] text-[13px] font-medium text-[#eef0f4] inline-flex items-center gap-2 transition-colors"
        >
          {actionIcon}
          <span>{actionLabel}</span>
        </button>
      )}
    </div>
  );
};
