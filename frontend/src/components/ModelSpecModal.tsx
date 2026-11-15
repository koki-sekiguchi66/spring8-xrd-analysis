import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { Button } from './ui/Button';

export interface ModelSpecModalProps {
  open: boolean;
  onClose: () => void;
}

/** Concise engineering specification sheet for the Voigt engine and physical constraints. */
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
      title: 'Voigt 独立幅最適化 (Origin70互換)',
      accent: 'text-sky-300',
      detail:
        'ガウス幅 wG とローレンツ幅 wL に独立の vary=True を設定し、Olivero-Longbothum 式で合成半値幅 FWHM を算出します。',
    },
    {
      title: 'bcc211 による Bragg 幾何拘束',
      accent: 'text-amber-300',
      detail:
        '孤立ピーク bcc211 から θ_110 = arcsin(sin(θ_211) / √3) および tan(θ_110) / tan(θ_211) 比で重畳 bcc110 を拘束します。',
    },
    {
      title: '局所直線 BG 減算と再現性',
      accent: 'text-emerald-300',
      detail:
        '切り出し範囲両端10点平均を結ぶ局所直線BGを差し引き、random.seed(42) で決定論的なフィッティングを実行します。',
    },
    {
      title: '相分率・転位密度算出',
      accent: 'text-[#eceef2]',
      detail:
        '多重度・構造因子・LP因子補正済みの積分強度比から f_α\' を算出し、Modified Williamson-Hall 法で転位密度 ρ を求めます。',
    },
  ];

  const shortcuts = [
    { keys: 'Ctrl + K', desc: 'クイック移動・コマンドパレット' },
    { keys: 'Ctrl + B', desc: 'エクスプローラー表示切替' },
    { keys: 'Ctrl + `', desc: '出力コンソール表示切替' },
    { keys: 'Esc', desc: 'モーダルを閉じる' },
  ];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="解析モデル仕様"
      className="fixed inset-0 z-50 bg-black/65 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="max-w-2xl w-full rounded-lg bg-[#16181d] border border-[#313642] shadow-2xl overflow-hidden select-text"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 py-3 border-b border-[#23262e] flex items-center justify-between bg-[#121418]">
          <h3 className="text-sm font-semibold text-[#eceef2]">
            解析エンジン仕様・ショートカット
          </h3>
          <Button
            variant="ghost"
            size="xs"
            onClick={onClose}
            aria-label="閉じる"
            className="px-1.5"
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {specs.map((item) => (
              <div
                key={item.title}
                className="p-3 rounded-md bg-[#0a0b0e] border border-[#23262e] space-y-1"
              >
                <div className={`text-xs font-semibold ${item.accent}`}>{item.title}</div>
                <p className="text-xs text-[#9ca3b0] leading-relaxed">{item.detail}</p>
              </div>
            ))}
          </div>

          <div className="rounded-md bg-[#0a0b0e] border border-[#23262e] p-3">
            <div className="text-xs font-semibold text-[#9ca3b0] mb-2">キーボードショートカット</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {shortcuts.map((sc) => (
                <div key={sc.keys} className="flex items-center justify-between text-xs">
                  <span className="text-[#9ca3b0]">{sc.desc}</span>
                  <kbd className="px-1.5 py-0.5 rounded bg-[#16181d] border border-[#2a2e38] font-mono text-[11px] text-[#eceef2]">
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
