import React from 'react';
import { cn } from '../../lib/utils';

export interface MetricCellProps {
  label: string;
  value: React.ReactNode;
  unit?: string;
  meta?: React.ReactNode;
  tone?: 'default' | 'sky' | 'amber' | 'emerald';
  className?: string;
}

const VALUE_TONES = {
  default: 'text-[#eceef2]',
  sky: 'text-sky-300',
  amber: 'text-amber-300',
  emerald: 'text-emerald-300',
};

/** Single telemetry cell inside a segmented MetricStrip. */
export const MetricCell: React.FC<MetricCellProps> = ({
  label,
  value,
  unit,
  meta,
  tone = 'default',
  className,
}) => {
  return (
    <div className={cn('px-4 py-3 min-w-0', className)}>
      <div className="text-xs text-[#9ca3b0] truncate">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className={cn('text-xl font-semibold font-mono tabular-nums', VALUE_TONES[tone])}>
          {value}
        </span>
        {unit && <span className="text-xs font-mono text-[#636b78]">{unit}</span>}
      </div>
      {meta && <div className="mt-0.5 text-[11px] font-mono tabular-nums text-[#636b78] truncate">{meta}</div>}
    </div>
  );
};

export interface MetricStripProps {
  columns?: 2 | 3 | 4;
  children: React.ReactNode;
  className?: string;
}

/** Unified hairline-divided KPI bar replacing disconnected floating cards. */
export const MetricStrip: React.FC<MetricStripProps> = ({
  columns = 4,
  children,
  className,
}) => {
  const gridCols =
    columns === 2
      ? 'grid-cols-2'
      : columns === 3
      ? 'grid-cols-1 sm:grid-cols-3'
      : 'grid-cols-2 lg:grid-cols-4';

  return (
    <div
      className={cn(
        'rounded-lg bg-[#16181d] border border-[#23262e] grid divide-y sm:divide-y-0 sm:divide-x divide-[#23262e]',
        gridCols,
        className
      )}
    >
      {children}
    </div>
  );
};
