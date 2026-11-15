import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Search, CornerDownLeft } from 'lucide-react';
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

/** VS Code / Linear style Ctrl+K command palette for fast navigation and workbench actions. */
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
      className="fixed inset-0 z-50 bg-black/60 flex items-start justify-center pt-[14vh] px-4"
      onClick={onClose}
      onKeyDown={handleKeyDown}
    >
      <div
        className="w-full max-w-lg rounded-lg bg-[#16181d] border border-[#313642] shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="h-11 px-3.5 border-b border-[#23262e] flex items-center gap-2.5">
          <Search className="size-4 text-[#636b78] shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="ステージ移動・機能を実行..."
            className="w-full bg-transparent text-[13px] text-[#eceef2] placeholder-[#636b78] focus:outline-none"
          />
          <kbd className="px-1.5 py-0.5 rounded bg-[#0a0b0e] border border-[#23262e] text-[10px] font-mono text-[#636b78]">
            ESC
          </kbd>
        </div>

        <div className="max-h-72 overflow-y-auto py-1.5">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-xs text-[#636b78]">一致する操作がありません</div>
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
                    'w-full px-3.5 py-2 text-left flex items-center justify-between gap-3 text-[13px] transition-colors',
                    selected ? 'bg-[#1c1f26] text-[#eceef2]' : 'text-[#9ca3b0]'
                  )}
                >
                  <span className="flex items-center gap-2.5 min-w-0">
                    {item.icon && <span className="text-[#9ca3b0] shrink-0">{item.icon}</span>}
                    <span className="truncate">{item.label}</span>
                    <span className="text-[11px] text-[#636b78] shrink-0">{item.group}</span>
                  </span>
                  {selected ? (
                    <CornerDownLeft className="size-3.5 text-sky-400 shrink-0" aria-hidden="true" />
                  ) : item.shortcut ? (
                    <kbd className="text-[11px] font-mono text-[#636b78] shrink-0">
                      {item.shortcut}
                    </kbd>
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
