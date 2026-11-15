import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CornerDownLeft, Search } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface CommandItem {
  id: string;
  label: string;
  group: string;
  shortcut?: string;
  icon?: React.ReactNode;
  onSelect: () => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  items: CommandItem[];
}

/** Raycast / Linear style Ctrl+K command launcher. */
export const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onClose, items }) => {
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIdx(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (it) => it.label.toLowerCase().includes(q) || it.group.toLowerCase().includes(q)
    );
  }, [items, query]);

  useEffect(() => {
    setActiveIdx(0);
  }, [query]);

  if (!open) return null;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => (filtered.length > 0 ? (i + 1) % filtered.length : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) =>
        filtered.length > 0 ? (i - 1 + filtered.length) % filtered.length : 0
      );
    } else if (e.key === 'Enter' && filtered[activeIdx]) {
      e.preventDefault();
      filtered[activeIdx].onSelect();
      onClose();
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="コマンドパレット"
      className="fixed inset-0 z-50 bg-black/65 flex items-start justify-center pt-[14vh] px-4"
      onClick={onClose}
      onKeyDown={handleKeyDown}
    >
      <div
        className="w-full max-w-lg rounded-md bg-[#15181e] border border-[#303644] shadow-[0_24px_48px_rgba(0,0,0,0.65),inset_0_1px_0_0_rgba(255,255,255,0.05)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="h-10 px-3 border-b border-[#22262f] flex items-center gap-2.5 bg-[#101216]">
          <Search className="size-3.5 text-[#5d6473] shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="検索 / コマンド..."
            className="w-full bg-transparent text-[12px] text-[#eef0f4] placeholder-[#5d6473] focus:outline-none"
          />
          <kbd className="px-1.5 py-0.5 rounded bg-[#08090c] border border-[#22262f] shadow-[inset_0_-1px_0_0_#1a1d25] text-[10px] font-mono text-[#5d6473]">
            ESC
          </kbd>
        </div>

        <div className="max-h-72 overflow-y-auto p-1.5 space-y-0.5">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-[11px] font-mono text-[#5d6473]">該当なし</div>
          ) : (
            filtered.map((item, idx) => {
              const selected = idx === activeIdx;
              return (
                <button
                  key={item.id}
                  type="button"
                  onMouseEnter={() => setActiveIdx(idx)}
                  onClick={() => {
                    item.onSelect();
                    onClose();
                  }}
                  className={cn(
                    'w-full px-2.5 py-2 rounded text-left flex items-center justify-between gap-3 text-[12px] transition-colors',
                    selected ? 'bg-[#1f242e] text-[#eef0f4]' : 'text-[#98a0ae]'
                  )}
                >
                  <span className="flex items-center gap-2 min-w-0">
                    {item.icon && (
                      <span className={cn('shrink-0', selected ? 'text-sky-400' : 'text-[#5d6473]')}>
                        {item.icon}
                      </span>
                    )}
                    <span className="truncate">{item.label}</span>
                  </span>
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="px-1.5 py-0.5 rounded bg-[#08090c] border border-[#22262f] text-[10px] text-[#5d6473]">
                      {item.group}
                    </span>
                    {selected ? (
                      <CornerDownLeft className="size-3 text-sky-400 shrink-0" aria-hidden="true" />
                    ) : item.shortcut ? (
                      <kbd className="px-1.5 py-0.5 rounded bg-[#08090c] border border-[#22262f] shadow-[inset_0_-1px_0_0_#1a1d25] text-[10px] font-mono text-[#858d9c]">
                        {item.shortcut}
                      </kbd>
                    ) : null}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
