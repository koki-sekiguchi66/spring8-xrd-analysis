import React from 'react';
import { cn } from '../../lib/utils';

export interface SegmentedOption<T extends string> {
  value: T;
  label: React.ReactNode;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  accent?: 'sky' | 'amber' | 'emerald' | 'neutral';
}

export interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (val: T) => void;
  size?: 'sm' | 'md';
  fullWidth?: boolean;
  ariaLabel?: string;
  className?: string;
}

const ACTIVE_ACCENT: Record<NonNullable<SegmentedOption<string>['accent']>, string> = {
  neutral:
    'bg-[#1e222b] text-[#eef0f4] border-[#313745] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_1px_2px_rgba(0,0,0,0.45)]',
  sky: 'bg-[#1a222d] text-sky-300 border-sky-500/40 shadow-[inset_0_1px_0_0_rgba(56,189,248,0.12),0_1px_2px_rgba(0,0,0,0.45)]',
  amber:
    'bg-[#231e16] text-amber-300 border-amber-500/40 shadow-[inset_0_1px_0_0_rgba(245,158,11,0.12),0_1px_2px_rgba(0,0,0,0.45)]',
  emerald:
    'bg-[#16231e] text-emerald-300 border-emerald-500/40 shadow-[inset_0_1px_0_0_rgba(52,211,153,0.12),0_1px_2px_rgba(0,0,0,0.45)]',
};

/** Raised-thumb inset pill switcher inspired by Linear and Raycast. */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  size = 'md',
  fullWidth = false,
  ariaLabel,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center p-[3px] rounded-lg bg-[#08090c] border border-[#262b36] gap-1',
        fullWidth && 'w-full',
        className
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        const accent = opt.accent ?? 'neutral';
        return (
          <button
            key={opt.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'inline-flex items-center justify-center gap-2 rounded-md border transition-all duration-150 whitespace-nowrap select-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500/70',
              size === 'sm' ? 'h-8 px-3 text-[12px]' : 'h-9 px-4 text-[13px]',
              fullWidth && 'flex-1',
              active
                ? cn('font-semibold', ACTIVE_ACCENT[accent])
                : 'border-transparent text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#14171f] font-medium'
            )}
          >
            {opt.icon && <span className="shrink-0">{opt.icon}</span>}
            <span>{opt.label}</span>
            {opt.badge !== undefined && opt.badge !== null && (
              <span
                className={cn(
                  'px-1.5 rounded text-[11px] font-mono tabular-nums leading-4',
                  active ? 'bg-black/35 text-[#eef0f4]' : 'bg-[#15181e] text-[#858d9c]'
                )}
              >
                {opt.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
