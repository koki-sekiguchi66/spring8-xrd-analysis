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
  default: 'text-[#eef0f4]',
  sky: 'text-sky-300',
  amber: 'text-amber-300',
  emerald: 'text-emerald-300',
};

const TICK_TONES = {
  default: 'bg-[#3d4454]',
  sky: 'bg-sky-400',
  amber: 'bg-amber-400',
  emerald: 'bg-emerald-400',
};

/** Single telemetry readout inside a unified MetricStrip. */
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
      <div className="flex items-center gap-2 text-[12px] text-[#98a0ae] truncate">
        <span className={cn('w-1.5 h-3.5 rounded-full shrink-0', TICK_TONES[tone])} />
        <span className="truncate font-medium">{label}</span>
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5 pl-3">
        <span
          className={cn(
            'text-[22px] leading-tight font-semibold font-mono tabular-nums',
            VALUE_TONES[tone]
          )}
        >
          {value}
        </span>
        {unit && <span className="text-[12px] font-mono text-[#7c8494]">{unit}</span>}
      </div>
      {meta && (
        <div className="mt-1 pl-3 text-[11px] font-mono tabular-nums text-[#7c8494] truncate">
          {meta}
        </div>
      )}
    </div>
  );
};

export interface MetricStripProps {
  columns?: 2 | 3 | 4;
  children: React.ReactNode;
  className?: string;
}

/** Unified hairline-divided KPI bar with machined specular edge. */
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
        'rounded-md bg-[#15181e] border border-[#22262f] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.035)] grid divide-y sm:divide-y-0 sm:divide-x divide-[#22262f]',
        gridCols,
        className
      )}
    >
      {children}
    </div>
  );
};
