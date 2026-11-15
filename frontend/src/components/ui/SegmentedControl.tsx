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
  neutral: 'bg-[#1c1f26] text-[#eceef2] border-[#323743]',
  sky: 'bg-[#1c1f26] text-sky-300 border-sky-500/40',
  amber: 'bg-[#1c1f26] text-amber-300 border-amber-500/40',
  emerald: 'bg-[#1c1f26] text-emerald-300 border-emerald-500/40',
};

/** Accessible inset segmented switcher inspired by Linear and VS Code view toggles. */
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
        'inline-flex items-center p-0.5 rounded-lg bg-[#0a0b0e] border border-[#23262e] gap-0.5',
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
              'inline-flex items-center justify-center gap-1.5 rounded-md border transition-colors duration-150 whitespace-nowrap select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60',
              size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-[13px]',
              fullWidth && 'flex-1',
              active
                ? cn('font-semibold', ACTIVE_ACCENT[accent])
                : 'border-transparent text-[#9ca3b0] hover:text-[#eceef2] font-medium'
            )}
          >
            {opt.icon && <span className="shrink-0">{opt.icon}</span>}
            <span>{opt.label}</span>
            {opt.badge !== undefined && opt.badge !== null && (
              <span
                className={cn(
                  'px-1.5 py-0.2 rounded text-[11px] font-mono tabular-nums',
                  active ? 'bg-[#282d38] text-[#eceef2]' : 'bg-[#16181d] text-[#9ca3b0]'
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
