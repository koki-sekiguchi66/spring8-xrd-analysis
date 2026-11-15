import React, { useState } from 'react';
import {
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  BookOpen,
  Sparkles,
  Compass,
  MousePointerClick,
} from 'lucide-react';

export interface GuideStepItem {
  badge: string;
  title: string;
  description: string;
}

export interface GuideGlossaryItem {
  term: string;
  meaning: string;
}

export interface TutorialGuideBannerProps {
  mode: 'xrd' | 'dic';
  stepTitle: string;
  summary: string;
  steps: GuideStepItem[];
  glossary?: GuideGlossaryItem[];
  tip?: string;
}

export const TutorialGuideBanner: React.FC<TutorialGuideBannerProps> = ({
  mode,
  stepTitle,
  summary,
  steps,
  glossary = [],
  tip,
}) => {
  const [expanded, setExpanded] = useState<boolean>(true);
  const [showGlossary, setShowGlossary] = useState<boolean>(false);

  const isXrd = mode === 'xrd';

  const triggerSpotlightTour = (stepIndex = 0) => {
    window.dispatchEvent(
      new CustomEvent('xrd-start-tour', {
        detail: { stepIndex },
      })
    );
  };

  return (
    <div
      className={`rounded-2xl border shadow-lg transition-all duration-200 ${
        isXrd
          ? 'bg-gradient-to-r from-cyan-950/45 via-zinc-900/95 to-zinc-900/95 border-cyan-500/40'
          : 'bg-gradient-to-r from-amber-950/45 via-zinc-900/95 to-zinc-900/95 border-amber-500/40'
      }`}
    >
      {/* Header Bar */}
      <div className="px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              isXrd
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
            }`}
          >
            <Compass className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-bold tracking-wide ${
                  isXrd
                    ? 'bg-cyan-500/25 text-cyan-200 border border-cyan-400/40'
                    : 'bg-amber-500/25 text-amber-200 border border-amber-400/40'
                }`}
              >
                はじめてナビ・操作チュートリアル
              </span>
              <h2 className="text-base sm:text-lg font-bold text-zinc-100">{stepTitle}</h2>
            </div>
            <p className="text-sm text-zinc-300 mt-0.5">{summary}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => triggerSpotlightTour(0)}
            className={`px-3.5 py-2 rounded-xl font-extrabold text-sm flex items-center gap-2 shadow-md transition-all ${
              isXrd
                ? 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-zinc-950 shadow-cyan-500/20'
                : 'bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-zinc-950 shadow-amber-500/20'
            }`}
          >
            <MousePointerClick className="w-4 h-4" />
            <span>アニメーション操作ガイド（押す場所を実演）</span>
          </button>

          {glossary.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setExpanded(true);
                setShowGlossary((prev) => !prev);
              }}
              className="px-3.5 py-2 rounded-lg bg-zinc-800/90 hover:bg-zinc-700/80 border border-zinc-700 text-sm font-medium text-zinc-200 flex items-center gap-1.5 transition-colors"
            >
              <BookOpen className="w-4 h-4 text-cyan-400" />
              <span>用語・原理の解説</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="px-3.5 py-2 rounded-lg bg-zinc-800/90 hover:bg-zinc-700/80 border border-zinc-700 text-sm font-medium text-zinc-200 flex items-center gap-1.5 transition-colors"
          >
            <HelpCircle className="w-4 h-4 text-amber-400" />
            <span>{expanded ? 'ガイドを閉じる' : '操作手順を表示'}</span>
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Step-by-Step Cards */}
      {expanded && (
        <div className="px-5 pb-4 pt-1 space-y-3 border-t border-zinc-800/80">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
            {steps.map((st, idx) => (
              <div
                key={idx}
                onClick={() => triggerSpotlightTour(idx)}
                className="group cursor-pointer rounded-xl bg-zinc-950/75 hover:bg-zinc-900/95 border border-zinc-800/90 hover:border-cyan-500/50 p-3.5 flex flex-col justify-between gap-2.5 transition-all"
                title="クリックするとこの操作を行うボタン・パネルをアニメーションで光らせて案内します"
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`px-2.5 py-1 rounded-lg text-xs font-mono font-bold shrink-0 ${
                      isXrd
                        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    }`}
                  >
                    {st.badge}
                  </div>
                  <div className="space-y-1">
                    <div className="text-sm sm:text-base font-bold text-zinc-100 group-hover:text-cyan-300 transition-colors">
                      {st.title}
                    </div>
                    <p className="text-sm text-zinc-300 leading-relaxed">{st.description}</p>
                  </div>
                </div>
                <div className="flex items-center justify-end">
                  <span className="text-xs font-bold text-cyan-400/90 group-hover:text-cyan-300 flex items-center gap-1">
                    <MousePointerClick className="w-3.5 h-3.5" />
                    <span>画面上の場所を光らせて案内 ▶</span>
                  </span>
                </div>
              </div>
            ))}
          </div>

          {tip && (
            <div className="rounded-xl bg-zinc-950/60 border border-zinc-800 px-4 py-2.5 flex items-center gap-2.5 text-sm text-zinc-200">
              <Lightbulb className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                <strong className="text-amber-300">ワンポイント：</strong> {tip}
              </span>
            </div>
          )}

          {showGlossary && glossary.length > 0 && (
            <div className="rounded-xl bg-zinc-950/90 border border-zinc-700/80 p-4 space-y-2.5">
              <div className="flex items-center gap-2 text-sm font-bold text-cyan-300">
                <Sparkles className="w-4 h-4" />
                <span>初心者向け 専門用語・解析アルゴリズム解説</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {glossary.map((g, i) => (
                  <div key={i} className="p-3 rounded-lg bg-zinc-900/90 border border-zinc-800">
                    <div className="text-sm font-bold text-zinc-100">{g.term}</div>
                    <div className="text-sm text-zinc-300 mt-1 leading-relaxed">{g.meaning}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
