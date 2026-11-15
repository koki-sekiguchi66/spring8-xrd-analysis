import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface DisclosureProps {
  title: React.ReactNode;
  summary?: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  className?: string;
}

/** Compact property-inspector disclosure panel. */
export const Disclosure: React.FC<DisclosureProps> = ({
  title,
  summary,
  open,
  onToggle,
  children,
  className,
}) => {
  return (
    <div className={cn('rounded-lg bg-[#0a0b0e] border border-[#23262e] overflow-hidden', className)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="w-full h-9 px-3 flex items-center justify-between gap-2 text-[13px] font-medium text-[#eceef2] hover:bg-[#16181d] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60"
      >
        <span className="flex items-center gap-2 min-w-0 truncate">
          {open ? (
            <ChevronDown className="size-3.5 text-[#9ca3b0] shrink-0" aria-hidden="true" />
          ) : (
            <ChevronRight className="size-3.5 text-[#9ca3b0] shrink-0" aria-hidden="true" />
          )}
          <span className="truncate">{title}</span>
        </span>
        {summary && <span className="text-xs font-mono text-[#636b78] shrink-0">{summary}</span>}
      </button>
      {open && <div className="p-3 border-t border-[#23262e] bg-[#121418]">{children}</div>}
    </div>
  );
};
