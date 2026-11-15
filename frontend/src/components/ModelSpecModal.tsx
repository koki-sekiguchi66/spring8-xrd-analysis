import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { Button } from './ui/Button';

export interface ModelSpecModalProps {
  open: boolean;
  onClose: () => void;
}

/** Concise engineering specification sheet and keybindings reference. */
export const ModelSpecModal: React.FC<ModelSpecModalProps> = ({ open, onClose }) => {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const specs = [
    {
      title: 'Voigt 最適化',
      accent: 'text-sky-300',
      detail: 'wG / wL 独立最適化 (vary=True), Olivero-Longbothum FWHM',
    },
    {
      title: '原田スクリプト準拠',
      accent: 'text-amber-300',
      detail: '1Peak ver7.0 / MultiPeaks ver4.0.0 / 2PeaksRatio ver10 / 3PeaksLuders ver4, 前フレーム基準拘束・往復解析',
    },
    {
      title: '背景・再現性',
      accent: 'text-emerald-300',
      detail: '前処理 Rubberband + PCHIP のみ (窓内の背景項なし), seed(42) 固定による決定論的最適化',
    },
    {
      title: '相分率・転位密度',
      accent: 'text-[#eef0f4]',
      detail: "直接比較法 (Cromer-Mann・LP・DW・実測格子定数) による f_α', Modified W-H 転位密度 (半定量)",
    },
  ];

  const shortcuts = [
    { keys: 'Ctrl + K', desc: 'コマンドパレット' },
    { keys: 'Ctrl + B', desc: 'サイドバー切替' },
    { keys: 'Ctrl + `', desc: 'コンソール切替' },
    { keys: 'Esc', desc: 'モーダルを閉じる' },
  ];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="仕様・ショートカット"
      className="fixed inset-0 z-50 bg-black/65 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="max-w-xl w-full rounded-md bg-[#15181e] border border-[#303644] shadow-[0_24px_48px_rgba(0,0,0,0.65),inset_0_1px_0_0_rgba(255,255,255,0.05)] overflow-hidden select-text"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-3.5 py-2.5 border-b border-[#22262f] flex items-center justify-between bg-[#101216]">
          <h3 className="text-[12px] font-semibold text-[#eef0f4]">モデル仕様・ショートカット</h3>
          <Button variant="ghost" size="xs" onClick={onClose} aria-label="閉じる" className="px-1.5">
            <X className="size-3.5" aria-hidden="true" />
          </Button>
        </div>

        <div className="p-3.5 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {specs.map((item) => (
              <div
                key={item.title}
                className="p-2.5 rounded-md bg-[#08090c] border border-[#22262f] space-y-1"
              >
                <div className={`text-[11px] font-semibold ${item.accent}`}>{item.title}</div>
                <div className="text-[11px] font-mono text-[#858d9c] leading-relaxed">{item.detail}</div>
              </div>
            ))}
          </div>

          <div className="rounded-md bg-[#08090c] border border-[#22262f] p-2.5">
            <div className="text-[11px] font-medium text-[#858d9c] mb-2">ショートカット</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {shortcuts.map((sc) => (
                <div key={sc.keys} className="flex items-center justify-between text-[11px]">
                  <span className="text-[#98a0ae]">{sc.desc}</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-[#15181e] border border-[#262a34] shadow-[inset_0_-1px_0_0_#1a1d25] font-mono text-[10px] text-[#eef0f4]">
                    {sc.keys}
                  </kbd>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
