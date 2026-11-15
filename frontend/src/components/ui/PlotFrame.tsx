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
        'rounded-lg bg-gradient-to-b from-[#171b22] to-[#13161c] border border-[#272c37] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05),0_8px_24px_-12px_rgba(0,0,0,0.75)] flex flex-col overflow-hidden',
        className
      )}
    >
      <div className="px-4 py-2.5 border-b border-[#242934] flex flex-wrap items-center justify-between gap-2 bg-[#161a21]">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="w-2 h-2 rounded-full bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.65)] shrink-0" />
          <h3 className="text-[13px] font-semibold text-[#eef0f4] tracking-tight truncate">
            {title}
          </h3>
          {subtitle && (
            <span className="text-[11px] font-mono tabular-nums text-[#7c8494] truncate">
              {subtitle}
            </span>
          )}
        </div>
        {toolbar && <div className="flex items-center gap-2 shrink-0 flex-wrap">{toolbar}</div>}
      </div>

      {subbar && (
        <div className="px-4 py-2 border-b border-[#22262f] bg-[#101216]">{subbar}</div>
      )}

      <div className="bg-[#08090c] p-2 flex-1 min-h-0">{children}</div>
    </section>
  );
};
