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
      title: 'Voigt 独立幅最適化 (Origin 互換)',
      accent: 'text-sky-300',
      detail:
        'ガウス幅 wG とローレンツ幅 wL を独立に最適化し（lmfit の gamma=sigma 拘束を解除）、Olivero-Longbothum 式で合成半値幅 FWHM を算出します。',
    },
    {
      title: '原田スクリプト準拠の連続解析',
      accent: 'text-amber-300',
      detail:
        '1Peak=ver7.0、MultiPeaks=ver4.0.0、2PeaksRatio=ver10（冷間圧延材・変態前）、3PeaksLuders=ver4（冷間圧延材・変態後）。前フレーム基準の拘束、積分強度スケーリング、初期値からの逆向き→前向き解析を元スクリプトどおりに行います。',
    },
    {
      title: '背景処理と再現性',
      accent: 'text-emerald-300',
      detail:
        '背景は前処理（Rubberband + PCHIP）でのみ除去し、フィット窓では Voigt 成分だけを当てはめます（元スクリプトどおり。窓端直線の差し引きは行いません）。乱数は各フレームで seed=42 に固定します。',
    },
    {
      title: '相分率・転位密度算出',
      accent: 'text-[#eceef2]',
      detail:
        "直接比較法: R = p|F|²·LP·exp(-2Bs²)/V²（Cromer-Mann 散乱因子、実測格子定数）で I/R を相ごとに平均して f_α' を算出。同一反射の成分（bcc110a+bcc1102 等）は合算、変態開始前の新生 α' は 0 とみなします。転位密度は修正 Williamson-Hall 法による半定量値です。",
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
