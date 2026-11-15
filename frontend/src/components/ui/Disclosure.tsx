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

/** Compact collapsible inspector tray. */
export const Disclosure: React.FC<DisclosureProps> = ({
  title,
  summary,
  open,
  onToggle,
  children,
  className,
}) => {
  return (
    <div className={cn('rounded-md bg-[#08090c] border border-[#22262f] overflow-hidden', className)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="w-full h-8 px-2.5 flex items-center justify-between gap-2 text-[12px] font-medium text-[#eef0f4] hover:bg-[#15181e] transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-500/70"
      >
        <span className="flex items-center gap-1.5 min-w-0 truncate">
          {open ? (
            <ChevronDown className="size-3.5 text-[#858d9c] shrink-0" aria-hidden="true" />
          ) : (
            <ChevronRight className="size-3.5 text-[#858d9c] shrink-0" aria-hidden="true" />
          )}
          <span className="truncate">{title}</span>
        </span>
        {summary && <span className="text-[11px] font-mono text-[#5d6473] shrink-0">{summary}</span>}
      </button>
      {open && <div className="p-2.5 border-t border-[#22262f] bg-[#101216]">{children}</div>}
    </div>
  );
};
