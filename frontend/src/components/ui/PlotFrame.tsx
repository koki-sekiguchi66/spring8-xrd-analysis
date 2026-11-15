import React from 'react';
import { cn } from '../../lib/utils';

export interface PlotFrameProps {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  toolbar?: React.ReactNode;
  subbar?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/** Machined scientific chart housing with recessed plot well and flush control strip. */
export const PlotFrame: React.FC<PlotFrameProps> = ({
  title,
  subtitle,
  toolbar,
  subbar,
  children,
  className,
}) => {
  return (
    <section
      className={cn(
        'rounded-md bg-[#15181e] border border-[#22262f] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.035)] flex flex-col overflow-hidden',
        className
      )}
    >
      <div className="px-3.5 py-2 border-b border-[#22262f] flex flex-wrap items-center justify-between gap-2 bg-[#13161b]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400/70 shrink-0" />
          <h3 className="text-[12px] font-semibold text-[#eef0f4] tracking-tight truncate">
            {title}
          </h3>
          {subtitle && (
            <span className="text-[11px] font-mono tabular-nums text-[#5d6473] truncate">
              {subtitle}
            </span>
          )}
        </div>
        {toolbar && <div className="flex items-center gap-1.5 shrink-0 flex-wrap">{toolbar}</div>}
      </div>

      {subbar && (
        <div className="px-3.5 py-1.5 border-b border-[#22262f] bg-[#101216]">{subbar}</div>
      )}

      <div className="bg-[#08090c] p-1.5 flex-1 min-h-0">{children}</div>
    </section>
  );
};
