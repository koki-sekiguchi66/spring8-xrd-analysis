import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Compass,
  Crosshair,
  Minimize2,
  Maximize2,
  RotateCcw,
  X,
} from 'lucide-react';
import { cn } from '../lib/utils';

export type GuideMainMode = 'xrd' | 'dic';
export type GuideXrdStep = 1 | 2 | 3 | 4 | 5;

export interface GuideStateSnapshot {
  mainMode: GuideMainMode;
  xrdStep: GuideXrdStep;
  hasFolder: boolean;
  folderPickSeq: number;
  hasPreprocess: boolean;
  step2SubScreen: 'overview' | 'detail';
  hasBatchConfigs: boolean;
  hasBatchResults: boolean;
  hasPhysicsResult: boolean;
}

export interface GuideStepDef {
  id: string;
  title: string;
  targetName: string;
  description: string;
  hint: string;
  mode?: GuideMainMode;
  xrdStep?: GuideXrdStep;
  targetSelector: string;
  fallbackSelector?: string;
  isComplete: (s: GuideStateSnapshot, baselineFolderSeq: number) => boolean;
}

export const WORKFLOW_GUIDE_STEPS: GuideStepDef[] = [
  {
    id: 'folder',
    title: '解析ディレクトリの指定',
    targetName: '「選択」または「サンプル読込」',
    description:
      'まず .tth ファイルが入った解析フォルダを「選択」ボタンで指定（または「サンプル読込」をクリック）してください。',
    hint: 'フォルダを指定してもガイドは途切れず、自動で次の操作へ案内します。',
    mode: 'xrd',
    xrdStep: 1,
    targetSelector: '[data-guide="folder-select"]',
    isComplete: (s, baseSeq) =>
      s.folderPickSeq > baseSeq || s.hasPreprocess || (s.mainMode === 'xrd' && s.xrdStep >= 2),
  },
  {
    id: 'preprocess',
    title: 'スパイク除去・ベースライン除去を実行',
    targetName: '青い「実行」ボタン',
    description:
      'フォルダを指定できたら「実行」を押してください。右のグラフで補正後波形（赤）が 0 付近に平坦化されるか確認します。',
    hint: '実行中はライブ表示となり、完了後に次工程ボタンが現れます。',
    mode: 'xrd',
    xrdStep: 1,
    targetSelector: '[data-guide="preprocess-run"]',
    isComplete: (s) => s.hasPreprocess || (s.mainMode === 'xrd' && s.xrdStep >= 2),
  },
  {
    id: 'to_step2',
    title: 'Step 2「初期値」へ進む',
    targetName: '緑の「次へ: 初期値」ボタン',
    description:
      '前処理が完了したら「次へ: 初期値」をクリックして、代表フレームの自動ピーク検出と詳細フィッティング確認へ進みます。',
    hint: '上部の「2. 初期値」タブからもいつでも移動できます。',
    mode: 'xrd',
    xrdStep: 1,
    targetSelector: '[data-guide="step1-next"]',
    fallbackSelector: '[data-guide="nav-step-2"]',
    isComplete: (s) => s.mainMode === 'xrd' && s.xrdStep >= 2,
  },
  {
    id: 'step2_detail',
    title: '各ピークの詳細フィッティングを確認',
    targetName: '「詳細 Fit（ピーク別フィッティング確認）」タブ',
    description:
      '自動検出したピーク群が妥当か確かめるため、「詳細 Fit（ピーク別フィッティング確認）」タブ（またはカードの「詳細フィッティング・波形確認」ボタン）を開きましょう。',
    hint: '実測点・Voigt 合成曲線・残差・FWHM・2θ 範囲を対話的に検証・調整できます。',
    mode: 'xrd',
    xrdStep: 2,
    targetSelector: '[data-guide="step2-detail-tab"]',
    fallbackSelector: '[data-guide="nav-step-2"]',
    isComplete: (s) => s.step2SubScreen === 'detail' || s.xrdStep >= 3,
  },
  {
    id: 'step2_save',
    title: '初期値 Excel を保存して一括Fit へ',
    targetName: '右上の「保存して次へ」ボタン',
    description:
      '必要なピーク群にチェックを入れ詳細を確認したら、「保存して次へ」を押して初期値シートを保存し Step 3 へ進みます。',
    hint: '初期値が保存されると自動で Step 3 画面へ切り替わります。',
    mode: 'xrd',
    xrdStep: 2,
    targetSelector: '[data-guide="step2-save-next"]',
    isComplete: (s) => s.mainMode === 'xrd' && s.xrdStep >= 3,
  },
  {
    id: 'step3_batch',
    title: '全フレーム一括 Voigt フィッティング',
    targetName: '右上の「一括実行」ボタン',
    description:
      '右上の「一括実行」ボタンを押すと選択した全ピーク群の連続最適化が始まります。「モニター」表示で進捗波形を確認できます。',
    hint: '完了後「次へ: 検証」ボタンで外れ値チェック画面へ進みます。',
    mode: 'xrd',
    xrdStep: 3,
    targetSelector: '[data-guide="step3-run"]',
    isComplete: (s) => s.hasBatchResults && s.xrdStep >= 4,
  },
  {
    id: 'step4_review',
    title: '外れ値修正 ＆ 最終 Excel エクスポート',
    targetName: '「次へ: 物理量」または「トレンド・出力」',
    description:
      '残差が大きい外れ値フレームがあれば左リストから選んで「一括再Fit」、トレンド・出力タブで Excel 保存後に Step 5 へ進みます。',
    hint: '外れ値が 0 件ならそのまま Step 5「物理量」へ進んで問題ありません。',
    mode: 'xrd',
    xrdStep: 4,
    targetSelector: '[data-guide="step4-next"]',
    fallbackSelector: '[data-guide="nav-step-5"]',
    isComplete: (s) => s.mainMode === 'xrd' && s.xrdStep === 5,
  },
  {
    id: 'step5_physics',
    title: '相分率・転位密度・格子ひずみを算出',
    targetName: '「計算」ボタン',
    description:
      '装置・基準定数を確認して「計算」をクリックすると、α′ 相分率・Modified W-H 転位密度・格子ひずみのグラフと表を一括生成します。',
    hint: '上部の切替タブで「相分率」「転位密度」「格子ひずみ」「テーブル」を比較できます。',
    mode: 'xrd',
    xrdStep: 5,
    targetSelector: '[data-guide="step5-calc"]',
    isComplete: (s) => s.hasPhysicsResult,
  },
  {
    id: 'dic_mode',
    title: 'DIC 動画フレーム抽出モード切替',
    targetName: '右上「XRD 回折・相解析 / DIC 動画フレーム抽出」',
    description:
      '引張試験動画（MP4 / AVI）から DIC ひずみ計測用の連続静止画を切り出したいときは、右上の「DIC 動画フレーム抽出」モードに切り替えます。',
    hint: 'タイトルバー右上のスイッチャーでいつでも XRD 解析と DIC 抽出を行き来できます。',
    targetSelector: '[data-guide="mode-switcher"]',
    isComplete: (s) => s.mainMode === 'dic',
  },
];

interface TargetRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface WorkflowGuideProps {
  active: boolean;
  stepIndex: number;
  onStepChange: (nextIndex: number) => void;
  onNavigateTarget: (mode?: GuideMainMode, step?: GuideXrdStep) => void;
  onClose: () => void;
  stateSnapshot: GuideStateSnapshot;
}

/** Persistent, non-blocking animated walkthrough with live spotlight tracking. */
export const WorkflowGuide: React.FC<WorkflowGuideProps> = ({
  active,
  stepIndex,
  onStepChange,
  onNavigateTarget,
  onClose,
  stateSnapshot,
}) => {
  const [minimized, setMinimized] = useState(false);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [dockSide, setDockSide] = useState<'right' | 'left'>('right');
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [justCompletedMsg, setJustCompletedMsg] = useState<string | null>(null);
  const [pausedOnManualStep, setPausedOnManualStep] = useState(false);
  const baselineFolderSeqRef = useRef<number>(stateSnapshot.folderPickSeq);
  const latestSnapshotRef = useRef<GuideStateSnapshot>(stateSnapshot);
  latestSnapshotRef.current = stateSnapshot;
  const guideNavGuardRef = useRef<boolean>(false);
  const prevMilestonesRef = useRef({
    folderPickSeq: stateSnapshot.folderPickSeq,
    hasPreprocess: stateSnapshot.hasPreprocess,
    xrdStep: stateSnapshot.xrdStep,
    step2SubScreen: stateSnapshot.step2SubScreen,
    hasBatchResults: stateSnapshot.hasBatchResults,
    hasPhysicsResult: stateSnapshot.hasPhysicsResult,
    mainMode: stateSnapshot.mainMode,
  });

  const safeIdx = Math.max(0, Math.min(WORKFLOW_GUIDE_STEPS.length - 1, stepIndex));
  const currentStep = WORKFLOW_GUIDE_STEPS[safeIdx];

  const stepSatisfied = useMemo(
    () => currentStep.isComplete(stateSnapshot, baselineFolderSeqRef.current),
    [currentStep, stateSnapshot]
  );

  // Clear manual review pause whenever user performs any new real workflow action.
  useEffect(() => {
    const p = prevMilestonesRef.current;
    const progressChanged =
      p.folderPickSeq !== stateSnapshot.folderPickSeq ||
      p.hasPreprocess !== stateSnapshot.hasPreprocess ||
      p.step2SubScreen !== stateSnapshot.step2SubScreen ||
      p.hasBatchResults !== stateSnapshot.hasBatchResults ||
      p.hasPhysicsResult !== stateSnapshot.hasPhysicsResult;
    const viewChanged =
      p.xrdStep !== stateSnapshot.xrdStep || p.mainMode !== stateSnapshot.mainMode;

    if (progressChanged || viewChanged) {
      if (guideNavGuardRef.current && !progressChanged) {
        guideNavGuardRef.current = false;
      } else {
        guideNavGuardRef.current = false;
        setPausedOnManualStep(false);
      }
      prevMilestonesRef.current = {
        folderPickSeq: stateSnapshot.folderPickSeq,
        hasPreprocess: stateSnapshot.hasPreprocess,
        xrdStep: stateSnapshot.xrdStep,
        step2SubScreen: stateSnapshot.step2SubScreen,
        hasBatchResults: stateSnapshot.hasBatchResults,
        hasPhysicsResult: stateSnapshot.hasPhysicsResult,
        mainMode: stateSnapshot.mainMode,
      };
    }
  }, [stateSnapshot]);

  const measureTarget = useCallback(() => {
    if (!active) {
      setTargetRect(null);
      return;
    }
    let el = document.querySelector(currentStep.targetSelector) as HTMLElement | null;
    if (!el && currentStep.fallbackSelector) {
      el = document.querySelector(currentStep.fallbackSelector) as HTMLElement | null;
    }
    if (!el) {
      setTargetRect(null);
      return;
    }
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) {
      setTargetRect(null);
      return;
    }
    setTargetRect((prev) => {
      const next = {
        left: Math.round(r.left),
        top: Math.round(r.top),
        width: Math.round(r.width),
        height: Math.round(r.height),
      };
      if (
        prev &&
        prev.left === next.left &&
        prev.top === next.top &&
        prev.width === next.width &&
        prev.height === next.height
      ) {
        return prev;
      }
      return next;
    });
  }, [active, currentStep]);

  useEffect(() => {
    if (!active) return;
    measureTarget();

    let rafId = 0;
    const scheduleMeasure = () => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(measureTarget);
    };

    const mutationObserver = new MutationObserver(scheduleMeasure);
    mutationObserver.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style', 'data-guide'],
    });

    const resizeObserver = new ResizeObserver(scheduleMeasure);
    resizeObserver.observe(document.body);

    window.addEventListener('resize', scheduleMeasure);
    window.addEventListener('scroll', scheduleMeasure, true);
    const interval = window.setInterval(measureTarget, 300);

    return () => {
      cancelAnimationFrame(rafId);
      mutationObserver.disconnect();
      resizeObserver.disconnect();
      window.removeEventListener('resize', scheduleMeasure);
      window.removeEventListener('scroll', scheduleMeasure, true);
      window.clearInterval(interval);
    };
  }, [active, measureTarget]);

  useEffect(() => {
    if (!active || !autoAdvance || !stepSatisfied || pausedOnManualStep) return;
    if (safeIdx >= WORKFLOW_GUIDE_STEPS.length - 1) return;

    setJustCompletedMsg(`達成: ${currentStep.title}`);

    const timer = window.setTimeout(() => {
      // Scan with latestSnapshotRef so multi-step actions (like サンプル読込) sync cleanly
      const snap = latestSnapshotRef.current;
      let nextIdx = safeIdx + 1;
      for (let i = safeIdx + 1; i < WORKFLOW_GUIDE_STEPS.length; i++) {
        nextIdx = i;
        if (!WORKFLOW_GUIDE_STEPS[i].isComplete(snap, baselineFolderSeqRef.current)) {
          break;
        }
      }
      onStepChange(nextIdx);
      setJustCompletedMsg(null);
    }, 550);

    return () => window.clearTimeout(timer);
  }, [active, autoAdvance, stepSatisfied, pausedOnManualStep, safeIdx, currentStep.title, onStepChange]);

  const handleGoStep = (nextIdx: number, manualRewind = false) => {
    const clamped = Math.max(0, Math.min(WORKFLOW_GUIDE_STEPS.length - 1, nextIdx));
    setPausedOnManualStep(manualRewind || clamped < safeIdx);
    const stepDef = WORKFLOW_GUIDE_STEPS[clamped];
    const snap = latestSnapshotRef.current;
    const willSwitchView =
      (stepDef.mode && stepDef.mode !== snap.mainMode) ||
      (stepDef.xrdStep && stepDef.xrdStep !== snap.xrdStep);
    guideNavGuardRef.current = Boolean(willSwitchView);
    setJustCompletedMsg(null);
    if (stepDef.mode || stepDef.xrdStep) {
      onNavigateTarget(stepDef.mode, stepDef.xrdStep);
    }
    onStepChange(clamped);
    window.setTimeout(() => {
      const el = document.querySelector(stepDef.targetSelector) as HTMLElement | null;
      el?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    }, 90);
  };

  const handleFocusTarget = () => {
    if (currentStep.mode || currentStep.xrdStep) {
      onNavigateTarget(currentStep.mode, currentStep.xrdStep);
    }
    window.setTimeout(() => {
      const el =
        (document.querySelector(currentStep.targetSelector) as HTMLElement | null) ||
        (currentStep.fallbackSelector
          ? (document.querySelector(currentStep.fallbackSelector) as HTMLElement | null)
          : null);
      el?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
      measureTarget();
    }, 60);
  };

  if (!active) return null;

  const pad = 6;
  const ringLeft = targetRect ? Math.max(4, targetRect.left - pad) : 0;
  const ringTop = targetRect ? Math.max(4, targetRect.top - pad) : 0;
  const ringWidth = targetRect ? targetRect.width + pad * 2 : 0;
  const ringHeight = targetRect ? targetRect.height + pad * 2 : 0;
  const badgeRightSide =
    targetRect !== null &&
    typeof window !== 'undefined' &&
    ringHeight < 130 &&
    ringLeft + ringWidth + 200 < window.innerWidth &&
    ringLeft + ringWidth < window.innerWidth * 0.48;
  const badgeBelow = targetRect ? targetRect.top < 78 : false;

  return (
    <>
      {/* Non-blocking Animated Target Spotlight */}
      {targetRect && (
        <div className="fixed inset-0 pointer-events-none z-40 overflow-hidden" aria-hidden="true">
          {/* Outer Sonar Pulse */}
          <div
            style={{
              left: ringLeft,
              top: ringTop,
              width: ringWidth,
              height: ringHeight,
            }}
            className="fixed rounded-lg border-2 border-sky-400/80 animate-guide-sonar"
          />

          {/* Sharp Focus Halo & Brackets */}
          <div
            style={{
              left: ringLeft,
              top: ringTop,
              width: ringWidth,
              height: ringHeight,
            }}
            className="fixed rounded-lg border-2 border-sky-400 shadow-[0_0_24px_rgba(56,189,248,0.45),inset_0_0_12px_rgba(56,189,248,0.16)] transition-all duration-300 ease-out"
          >
            <span className="absolute -top-1 -left-1 w-2.5 h-2.5 border-t-2 border-l-2 border-white rounded-tl-sm" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 border-t-2 border-r-2 border-white rounded-tr-sm" />
            <span className="absolute -bottom-1 -left-1 w-2.5 h-2.5 border-b-2 border-l-2 border-white rounded-bl-sm" />
            <span className="absolute -bottom-1 -right-1 w-2.5 h-2.5 border-b-2 border-r-2 border-white rounded-br-sm" />

            {/* Floating Pointer Callout Tag */}
            <div
              className={cn(
                'absolute px-2.5 py-1 rounded-md bg-sky-500 text-zinc-950 text-[11px] font-bold tracking-tight whitespace-nowrap shadow-[0_6px_18px_rgba(14,165,233,0.45)] flex items-center gap-1.5 animate-guide-float',
                badgeRightSide
                  ? 'left-full ml-3 top-1/2 -translate-y-1/2'
                  : badgeBelow
                    ? 'top-full mt-2 right-0'
                    : 'bottom-full mb-1.5 right-0'
              )}
            >
              <Crosshair className="w-3.5 h-3.5 shrink-0" />
              <span>
                STEP {safeIdx + 1}/{WORKFLOW_GUIDE_STEPS.length} · ここを操作
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Floating Persistent Guide Card */}
      <div
        className={cn(
          'fixed bottom-9 z-50 pointer-events-auto transition-all duration-200',
          dockSide === 'right' ? 'right-4' : 'left-[64px]',
          minimized ? 'w-auto max-w-[360px]' : 'w-[min(392px,calc(100vw-2rem))]'
        )}
      >
        {minimized ? (
          <div className="rounded-lg bg-[#141820]/95 backdrop-blur-md border border-sky-500/45 shadow-[0_12px_32px_rgba(0,0,0,0.65)] px-3 py-2 flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse shrink-0" />
            <button
              type="button"
              onClick={() => setMinimized(false)}
              className="text-left text-[12px] font-medium text-[#eef0f4] hover:text-sky-300 truncate"
            >
              ガイド {safeIdx + 1}/{WORKFLOW_GUIDE_STEPS.length}: {currentStep.title}
            </button>
            <button
              type="button"
              onClick={() => setMinimized(false)}
              title="展開"
              className="h-6 px-2 rounded bg-sky-500/15 border border-sky-500/40 text-[11px] font-semibold text-sky-300 hover:bg-sky-500/25 shrink-0 inline-flex items-center gap-1"
            >
              <Maximize2 className="w-3 h-3" />
              <span>開く</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              title="ガイド終了"
              className="w-6 h-6 rounded flex items-center justify-center text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#1e232d] shrink-0"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <section className="rounded-xl bg-[#13171e]/95 backdrop-blur-md border border-sky-500/40 shadow-[0_20px_50px_rgba(0,0,0,0.8),inset_0_1px_0_0_rgba(255,255,255,0.07)] overflow-hidden">
            {/* Header Bar */}
            <div className="px-4 py-2.5 bg-[#181d26] border-b border-[#262c38] flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-6 h-6 rounded-md bg-sky-500/15 border border-sky-500/40 flex items-center justify-center shrink-0">
                  <Compass className="w-3.5 h-3.5 text-sky-300" />
                </span>
                <div className="min-w-0">
                  <div className="text-[12px] font-semibold text-[#eef0f4] tracking-tight truncate">
                    操作ナビゲーションガイド
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => setAutoAdvance((v) => !v)}
                  title="操作に応じて自動で次ステップへ進む"
                  className={cn(
                    'h-6 px-2 rounded text-[11px] font-medium border transition-colors',
                    autoAdvance
                      ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                      : 'bg-[#0e1116] border-[#262c38] text-[#858d9c]'
                  )}
                >
                  自動進行 {autoAdvance ? 'ON' : 'OFF'}
                </button>
                <button
                  type="button"
                  onClick={() => setDockSide((s) => (s === 'right' ? 'left' : 'right'))}
                  title="ガイド位置を左右切替"
                  className="h-6 px-2 rounded bg-[#0e1116] border border-[#262c38] text-[11px] text-[#98a0ae] hover:text-[#eef0f4]"
                >
                  {dockSide === 'right' ? '左へ' : '右へ'}
                </button>
                <button
                  type="button"
                  onClick={() => setMinimized(true)}
                  title="最小化"
                  className="w-6 h-6 rounded flex items-center justify-center text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#232936]"
                >
                  <Minimize2 className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  title="ガイドを閉じる"
                  className="w-6 h-6 rounded flex items-center justify-center text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#232936]"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Interactive 9-Step Timeline Bar */}
            <div className="px-4 py-2 bg-[#0b0d12] border-b border-[#222630] flex items-center gap-1.5">
              {WORKFLOW_GUIDE_STEPS.map((st, idx) => {
                const isCurr = idx === safeIdx;
                const isDone = st.isComplete(stateSnapshot, baselineFolderSeqRef.current);
                return (
                  <button
                    key={st.id}
                    type="button"
                    onClick={() => handleGoStep(idx, idx <= safeIdx)}
                    title={`${idx + 1}. ${st.title}`}
                    className={cn(
                      'flex-1 h-2 rounded-full transition-all',
                      isCurr
                        ? 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.75)]'
                        : isDone
                          ? 'bg-emerald-400/75 hover:bg-emerald-400'
                          : 'bg-[#232833] hover:bg-[#353d4f]'
                    )}
                  />
                );
              })}
            </div>

            {/* Main Body */}
            <div className="p-3.5 space-y-2.5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-sky-500/15 border border-sky-500/35 text-[11px] font-mono font-bold text-sky-300 tabular-nums">
                      STEP {String(safeIdx + 1).padStart(2, '0')} / {WORKFLOW_GUIDE_STEPS.length}
                    </span>
                    {justCompletedMsg ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-300 animate-pulse">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>{justCompletedMsg}</span>
                      </span>
                    ) : stepSatisfied ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-300">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>操作完了</span>
                      </span>
                    ) : null}
                  </div>
                  <h4 className="mt-1.5 text-[14px] font-semibold text-[#eef0f4] tracking-tight">
                    {currentStep.title}
                  </h4>
                </div>
              </div>

              {/* Target Button/Element Indicator */}
              <button
                type="button"
                onClick={handleFocusTarget}
                className="w-full px-3 py-1.5 rounded-lg bg-[#0a0c10] border border-sky-500/35 hover:border-sky-400/70 flex items-center justify-between gap-2 text-left transition-colors group"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Crosshair className="w-3.5 h-3.5 text-sky-400 shrink-0 group-hover:scale-110 transition-transform" />
                  <span className="text-[11px] text-[#98a0ae] shrink-0">対象:</span>
                  <span className="text-[12px] font-semibold text-sky-300 truncate">
                    {currentStep.targetName}
                  </span>
                </div>
                <span className="text-[11px] font-mono text-[#7c8494] group-hover:text-sky-300 shrink-0">
                  表示
                </span>
              </button>

              <p className="text-[12.5px] leading-relaxed text-[#cfd4de]">
                {currentStep.description}
              </p>

              <div className="px-2.5 py-1.5 rounded-md bg-[#181c24] border border-[#252a36] text-[11.5px] text-[#98a0ae]">
                {currentStep.hint}
              </div>

              {/* Footer Controls */}
              <div className="pt-0.5 flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => handleGoStep(0, true)}
                  className="h-8 px-2.5 rounded-md text-[12px] text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#1e232d] inline-flex items-center gap-1.5"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>最初から</span>
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={safeIdx === 0}
                    onClick={() => handleGoStep(safeIdx - 1, true)}
                    className="h-8 px-3 rounded-md bg-[#1d222c] border border-[#2d3442] text-[12px] font-medium text-[#eef0f4] hover:bg-[#252b37] disabled:opacity-40 disabled:cursor-not-allowed inline-flex items-center gap-1"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                    <span>前へ</span>
                  </button>

                  {safeIdx < WORKFLOW_GUIDE_STEPS.length - 1 ? (
                    <button
                      type="button"
                      onClick={() => handleGoStep(safeIdx + 1)}
                      className="h-8 px-3.5 rounded-md bg-gradient-to-b from-sky-400 to-sky-500 text-zinc-950 font-semibold text-[12px] hover:from-sky-300 hover:to-sky-400 shadow-[0_2px_10px_rgba(56,189,248,0.3)] inline-flex items-center gap-1"
                    >
                      <span>次へ</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={onClose}
                      className="h-8 px-3.5 rounded-md bg-gradient-to-b from-emerald-400 to-emerald-500 text-zinc-950 font-semibold text-[12px] hover:from-emerald-300 hover:to-emerald-400"
                    >
                      完了して閉じる
                    </button>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}
      </div>
    </>
  );
};
