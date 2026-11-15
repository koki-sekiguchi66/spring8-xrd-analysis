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

/** Bespoke scientific plot housing with integrated header toolbar and inset chart canvas. */
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
        'rounded-lg bg-[#16181d] border border-[#23262e] flex flex-col overflow-hidden',
        className
      )}
    >
      <div className="px-4 py-2.5 border-b border-[#23262e] flex flex-wrap items-center justify-between gap-2 bg-[#16181d]">
        <div className="flex items-baseline gap-2.5 min-w-0">
          <h3 className="text-[13px] font-semibold text-[#eceef2] truncate">{title}</h3>
          {subtitle && (
            <span className="text-xs font-mono tabular-nums text-[#636b78] truncate">
              {subtitle}
            </span>
          )}
        </div>
        {toolbar && <div className="flex items-center gap-2 shrink-0 flex-wrap">{toolbar}</div>}
      </div>

      {subbar && (
        <div className="px-3.5 py-2 border-b border-[#23262e] bg-[#121418]">{subbar}</div>
      )}

      <div className="bg-[#0a0b0e] p-2 flex-1 min-h-0">{children}</div>
    </section>
  );
};
