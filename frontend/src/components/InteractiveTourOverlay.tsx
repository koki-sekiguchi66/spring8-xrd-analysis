import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Sparkles,
  ChevronLeft,
  ChevronRight,
  X,
  MousePointerClick,
  Sliders,
  Eye,
  Compass,
  Play,
  CheckCircle2,
  HelpCircle,
} from 'lucide-react';

export type TourSceneKey =
  | 'xrd-step-1'
  | 'xrd-step-2'
  | 'xrd-step-3'
  | 'xrd-step-4'
  | 'xrd-step-5'
  | 'dic-mode';

export type TourStepCategory = 'button' | 'parameter' | 'detail' | 'navigation';

export interface InteractiveTourStep {
  id: string;
  targetSelector: string;
  category: TourStepCategory;
  badgeText: string;
  title: string;
  description: string;
  subHint?: string;
  allowAutoClick?: boolean;
  autoClickLabel?: string;
}

export const TOUR_STEPS_BY_SCENE: Record<TourSceneKey, InteractiveTourStep[]> = {
  'xrd-step-1': [
    {
      id: 's1-folder',
      targetSelector: '[data-tour="step1-folder-select"]',
      category: 'button',
      badgeText: '👆 押すボタン案内 ①',
      title: '測定データフォルダを選択（またはサンプルデータ読込）',
      description:
        'まずここにある「フォルダを参照...」ボタンを押して、SPring-8 等の測定データ（.tth または .csv）が入ったフォルダを選択します。すぐに試したい場合は右隣の「Seki_age_2_tensile（サンプル）」ボタンを押してください。',
      subHint: '出力される初期値Excelや最終結果Excelも、ここで選んだフォルダの中に自動保存されます。',
      allowAutoClick: false,
    },
    {
      id: 's1-params',
      targetSelector: '[data-tour="step1-advanced-params"]',
      category: 'parameter',
      badgeText: '⚙️ パラメータ調節場所',
      title: 'BG除去・スパイク除去の詳細パラメータ調整（開閉式）',
      description:
        'バックグラウンド（BG）除去の開始角度（th_min = 12.1°）や、宇宙線・検出器ノイズのスパイク除去閾値（1.8倍）、谷点探索間隔（50点）を調節したい場合は、このパネルをクリックして展開します。',
      subHint: '通常はデフォルト値のままで Origin 互換の高精度な arPLS ベースライン除去が行われます。',
      allowAutoClick: true,
      autoClickLabel: 'パラメータ設定パネルを開閉してみる',
    },
    {
      id: 's1-run',
      targetSelector: '[data-tour="step1-run-btn"]',
      category: 'button',
      badgeText: '👆 押すボタン案内 ②（メイン実行）',
      title: '「.tth 自動仕分け ＆ 全ファイルBG除去を一括実行」を押す',
      description:
        'フォルダを指定したら、この青いメイン実行ボタンを押します。全ファイルの自動仕分け（tth/）・スパイク除去・arPLS バックグラウンド除去が一括で高速実行されます。',
      subHint: 'すでに処理済みのフォルダでは、キャッシュを利用して瞬時に読み込みが完了します。',
      allowAutoClick: true,
      autoClickLabel: 'この一括前処理ボタンを押して実行する',
    },
    {
      id: 's1-preview',
      targetSelector: '[data-tour="step1-preview-plot"]',
      category: 'detail',
      badgeText: '🔍 詳細確認エリア',
      title: 'BG除去前後のプロファイル比較＆フレーム番号スライダー確認',
      description:
        '前処理が終わると、ここに「元データ（Raw）」「推定ベースライン」「BG除去後データ」の重ね描きグラフが表示されます。上部のスライダーを動かして任意のフレーム番号（num）の波形品質を詳細確認でき、右下のボタンから Step 2 へ進めます。',
      subHint: 'グラフ上をドラッグすると拡大ズーム、ダブルクリックで全体表示に戻ります。',
    },
  ],
  'xrd-step-2': [
    {
      id: 's2-tabs',
      targetSelector: '[data-tour="step2-subscreen-tabs"]',
      category: 'detail',
      badgeText: '🔍 サブ画面切替タブ',
      title: '「全体プロファイル選択」と「拡大Voigtフィット確認・微調整」の切替',
      description:
        'Step 2 は画面がごちゃつかないよう2つのサブ画面に分かれています。左タブで全角度域のピーク候補を選び、右タブ「② 個別ピーク拡大Voigtフィット確認・微調整」に切り替えると、選択したピークの拡大波形と数値を精密チェックできます。',
      subHint: 'いつでもこのタブで全体俯瞰と個別ピーク詳細を行き来できます。',
    },
    {
      id: 's2-cards',
      targetSelector: '[data-tour="step2-candidate-cards"]',
      category: 'parameter',
      badgeText: '⚙️ ピーク候補選択＆詳細確認',
      title: 'ピーク・ペア候補カードの選択と「拡大Voigtフィット確認」ボタン',
      description:
        'fcc111+bcc110 などの各結晶面グループについて、自動検出された初期ピーク候補カードをクリックします。カード内の「拡大Voigtフィット波形を確認・微調整 ▶」ボタンを押すと、ローレンツ幅（wL）やガウス幅（wG）を直接編集できる詳細画面へジャンプします。',
      subHint: 'マルテンサイト未変態フレームでは α\'-BCC 相の振幅が 0 として物理的に正しく初期化されます。',
    },
    {
      id: 's2-save',
      targetSelector: '[data-tour="step2-save-proceed-btn"]',
      category: 'button',
      badgeText: '👆 押すボタン案内（保存して次へ）',
      title: '「採用初期値を _initial.xlsx に保存して Step 3 へ」を押す',
      description:
        '各ピークの初期値候補を確認したら、この緑色のボタンを押します。解析対象フォルダ直下に「試験片名_initial.xlsx」が出力され、自動的に Step 3（連続フィッティング設定）へ進みます。',
      allowAutoClick: true,
      autoClickLabel: '初期値を保存して Step 3 へ進む',
    },
  ],
  'xrd-step-3': [
    {
      id: 's3-tabs',
      targetSelector: '[data-tour="step3-subscreen-tabs"]',
      category: 'detail',
      badgeText: '🔍 サブ画面切替タブ',
      title: '「① エンジン＆拘束条件設定」と「② リアルタイム波形モニター」',
      description:
        '実行前は「① エンジン＆拘束条件設定」で各ピークの解析モードや物理拘束を設定し、実行開始すると自動的に「② リアルタイム波形＆推移モニター」へ切り替わって進捗と2θ・FWHM推移をライブ表示します。',
    },
    {
      id: 's3-config',
      targetSelector: '[data-tour="step3-group-config"]',
      category: 'parameter',
      badgeText: '⚙️ パラメータ・物理拘束の調節場所',
      title: 'bcc211 物理拘束オプション＆パラメータ詳細ドロワー',
      description:
        'ここで「独立ピーク bcc211 から bcc110 の中心・FWHM を物理拘束（Bragg 幾何学式＋tanθ比）」の ON/OFF や許容幅 Δθ_tol を調節できます。また各カードの「パラメータ詳細を編集」ボタンを押すと、マルテンサイト出現番号（DIMT_onset_num）や前フレーム比の許容倍率（振幅 0.80〜1.25、幅 0.70〜1.40）を個別に微調整できます。',
      subHint: 'bcc211 物理拘束を ON にすると、バックエンドが自動的に bcc211 を先に解析して bcc110 をガイドします。',
    },
    {
      id: 's3-start',
      targetSelector: '[data-tour="step3-start-btn"]',
      category: 'button',
      badgeText: '👆 押すボタン案内（連続解析スタート）',
      title: '「全ファイル連続解析スタート」ボタンを押す',
      description:
        '設定を確認したら、このボタンを押して全フレーム連続 Voigt フィッティングを開始します。局所直線BG減算・乱数シード固定（seed=42）・ガウス幅/ローレンツ幅の独立最適化が全ファイルに対して自動実行されます。',
      allowAutoClick: true,
      autoClickLabel: '連続フィッティングを開始する',
    },
  ],
  'xrd-step-4': [
    {
      id: 's4-tabs',
      targetSelector: '[data-tour="step4-subscreen-tabs"]',
      category: 'detail',
      badgeText: '🔍 サブ画面切替タブ',
      title: '「① 要確認フィット一括選択＆個別修復」と「② 全ピーク推移グラフ」',
      description:
        'Step 4 では、残差（residual）や隣接フレーム変化率から自動抽出された「要確認フレーム」を修復する画面と、全フレームの 2θ・強度 I・wG・wL・FWHM・residual の推移グラフを詳細チェックする画面を切り替えられます。',
    },
    {
      id: 's4-batch-select',
      targetSelector: '[data-tour="step4-batch-select"]',
      category: 'button',
      badgeText: '👆 押すボタン案内 ①（相別・全件一括選択）',
      title: '要確認 num の各相を「すべて一括選択」または「相別選択」',
      description:
        '抽出されたすべての要確認フィット（num × 相）を1クリックで選択できます。「すべて一括選択」のほか、「γ-FCC相のみ一括選択」「α\'-BCC相のみ一括選択」ボタンで対象相を絞り込むことも可能です。',
      allowAutoClick: true,
      autoClickLabel: '要確認アイテムをすべて一括選択する',
    },
    {
      id: 's4-batch-refit',
      targetSelector: '[data-tour="step4-batch-refit-btn"]',
      category: 'parameter',
      badgeText: '⚙️ 一括スマート再フィット＆個別パラメータ微調整',
      title: '「選択した件数を一括スマート再フィット」と個別微調整ワークベンチ',
      description:
        '一括選択した状態でこの紫色のボタンを押すと、前後の正常フレームの内挿ガイドを用いて全選択アイテムを一括再フィットします。また下のワークベンチでは、特定の num の 2θ・振幅・wG・wL の初期値と上下限（min/max）を手動で数値入力して単一再フィットすることもできます。',
    },
    {
      id: 's4-export',
      targetSelector: '[data-tour="step4-export-btn"]',
      category: 'button',
      badgeText: '👆 押すボタン案内 ②（Excel保存＆物理グラフへ）',
      title: '「output.xlsx 保存・更新」と「Step 5: 物理量・転位密度グラフへ」',
      description:
        '修復結果は解析対象フォルダ内の「試験片名output.xlsx」へ保存されます。右隣の「Step 5: 相分率・転位密度解析へ進む」ボタンを押すと、OUTPUTデータからマルテンサイト相分率や転位密度変化を自動計算してグラフ表示します。',
    },
  ],
  'xrd-step-5': [
    {
      id: 's5-params',
      targetSelector: '[data-tour="step5-params-bar"]',
      category: 'parameter',
      badgeText: '⚙️ 物理定数・既存Excel読込の調節場所',
      title: '物理定数（波長・バーガースベクトル・装置幅）設定と既存Excel読込',
      description:
        '右上の「物理定数・装置幅の設定」ボタンを押すと、SPring-8 のX線波長 λ、バーガースベクトル b、装置関数幅、基準フレーム num をいつでも変更して即時再計算できます。また「既存の output.xlsx を開く」から過去の解析結果Excelを直接読み込んでグラフ化することも可能です。',
    },
    {
      id: 's5-graphs',
      targetSelector: '[data-tour="step5-graph-tabs"]',
      category: 'detail',
      badgeText: '🔍 4種類の物理グラフ＆一覧表切替',
      title: 'マルテンサイト相分率 f_α\'・各相の転位密度 ρ・格子ひずみ ε の切替確認',
      description:
        'この4つの大型タブをクリックして、「① マルテンサイト相分率の推移」「② γ-FCC / α\'-BCC 各相の転位密度 ρ の変化（対数表示切替可）」「③ 各結晶面の弾性格子ひずみ ε_hkl」「④ 算出物理量テーブル＆CSV出力」を自由に切り替えて確認・出力できます。',
    },
  ],
  'dic-mode': [
    {
      id: 'dic-source',
      targetSelector: '[data-tour="dic-mode-select"]',
      category: 'button',
      badgeText: '👆 押すボタン案内 ①（動画入力選択）',
      title: '単一動画またはフォルダ一括モードを選び、「参照...」で動画を指定',
      description:
        '1本の動画から切り出す場合は「単一動画ファイル」、フォルダ内の全動画を一括処理する場合は「フォルダ一括処理」を選び、「ファイルを参照...」ボタンから引張試験動画（.mp4 / .avi 等）を選択します。',
    },
    {
      id: 'dic-params',
      targetSelector: '[data-tour="dic-timing-params"]',
      category: 'parameter',
      badgeText: '⚙️ 切り出し秒数・間隔の調節場所',
      title: '開始秒数（start_sec）・終了秒数（stop_sec）・切り出し間隔（step_sec）の調整',
      description:
        '動画を読み込むと総秒数とFPSが自動取得されます。ここで何秒から何秒まで、何秒おき（例: 1.0秒間隔、0.5秒間隔）に静止画を切り出すか、および保存形式（TIFF / PNG / JPG）を設定します。',
    },
    {
      id: 'dic-run',
      targetSelector: '[data-tour="dic-run-btn"]',
      category: 'button',
      badgeText: '👆 押すボタン案内 ②（フレーム一括抽出）',
      title: '「フレーム画像の一括切り出しを実行」ボタンを押す',
      description:
        'このボタンを押すと OpenCV エンジンが指定時刻へ高速シークし、日本語パスにも対応した安全なエンコード処理で連番画像ファイルを一括出力します。完了後は出力フォルダのパスが下に表示されます。',
    },
  ],
};

export interface InteractiveTourOverlayProps {
  sceneKey: TourSceneKey;
  isOpen: boolean;
  initialStepIndex?: number;
  onClose: () => void;
  onSwitchScene?: (scene: TourSceneKey) => void;
}

interface TargetRect {
  top: number;
  left: number;
  width: number;
  height: number;
  bottom: number;
  right: number;
}

export const InteractiveTourOverlay: React.FC<InteractiveTourOverlayProps> = ({
  sceneKey,
  isOpen,
  initialStepIndex = 0,
  onClose,
  onSwitchScene,
}) => {
  const steps = TOUR_STEPS_BY_SCENE[sceneKey] || [];
  const [currentStepIdx, setCurrentStepIdx] = useState<number>(initialStepIndex);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [viewport, setViewport] = useState<{ w: number; h: number }>({
    w: typeof window !== 'undefined' ? window.innerWidth : 1440,
    h: typeof window !== 'undefined' ? window.innerHeight : 900,
  });
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    setCurrentStepIdx(Math.min(initialStepIndex, Math.max(0, steps.length - 1)));
  }, [sceneKey, initialStepIndex, steps.length]);

  const currentStep = steps[currentStepIdx] || steps[0];

  const updateTargetPosition = useCallback((scrollIntoView = false) => {
    if (!isOpen || !currentStep) return;
    const el = document.querySelector(currentStep.targetSelector) as HTMLElement | null;
    setViewport({ w: window.innerWidth, h: window.innerHeight });

    if (!el) {
      setTargetRect(null);
      return;
    }

    if (scrollIntoView) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    }

    const rect = el.getBoundingClientRect();
    const pad = 8;
    setTargetRect({
      top: Math.max(4, rect.top - pad),
      left: Math.max(4, rect.left - pad),
      width: Math.min(window.innerWidth - 8, rect.width + pad * 2),
      height: Math.min(window.innerHeight - 8, rect.height + pad * 2),
      bottom: rect.bottom + pad,
      right: rect.right + pad,
    });
  }, [isOpen, currentStep]);

  useEffect(() => {
    if (!isOpen) return;
    updateTargetPosition(true);

    const timer1 = window.setTimeout(() => updateTargetPosition(false), 260);
    const timer2 = window.setTimeout(() => updateTargetPosition(false), 550);

    const handleResizeOrScroll = () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => updateTargetPosition(false));
    };

    window.addEventListener('resize', handleResizeOrScroll, true);
    window.addEventListener('scroll', handleResizeOrScroll, true);

    return () => {
      window.clearTimeout(timer1);
      window.clearTimeout(timer2);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', handleResizeOrScroll, true);
      window.removeEventListener('scroll', handleResizeOrScroll, true);
    };
  }, [isOpen, currentStepIdx, sceneKey, updateTargetPosition]);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowRight') {
        setCurrentStepIdx((prev) => Math.min(steps.length - 1, prev + 1));
      } else if (e.key === 'ArrowLeft') {
        setCurrentStepIdx((prev) => Math.max(0, prev - 1));
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose, steps.length]);

  if (!isOpen || !currentStep) return null;

  const handleAutoClickTarget = () => {
    const el = document.querySelector(currentStep.targetSelector) as HTMLElement | null;
    if (el) {
      // Find clickable button inside or click element itself
      const btn =
        el.tagName === 'BUTTON'
          ? el
          : (el.querySelector('button:not([disabled])') as HTMLElement | null) || el;
      btn.click();
      setTimeout(() => updateTargetPosition(false), 200);
    }
    if (currentStepIdx < steps.length - 1) {
      setCurrentStepIdx((prev) => prev + 1);
    }
  };

  // Compute smart coachmark card placement
  const cardWidth = Math.min(480, viewport.w - 32);
  let cardTop = Math.max(24, viewport.h / 2 - 160);
  let cardLeft = Math.max(16, viewport.w / 2 - cardWidth / 2);
  let pointerPlacement: 'top' | 'bottom' | 'none' = 'none';

  if (targetRect) {
    const spaceBelow = viewport.h - targetRect.bottom;
    const spaceAbove = targetRect.top;

    cardLeft = Math.min(
      Math.max(20, targetRect.left + targetRect.width / 2 - cardWidth / 2),
      viewport.w - cardWidth - 20
    );

    if (spaceBelow >= 285 || spaceBelow >= spaceAbove) {
      cardTop = Math.min(viewport.h - 295, targetRect.bottom + 26);
      pointerPlacement = 'top';
    } else {
      cardTop = Math.max(16, targetRect.top - 285);
      pointerPlacement = 'bottom';
    }
  }

  const categoryColor =
    currentStep.category === 'button'
      ? {
          ring: 'border-cyan-400 shadow-[0_0_35px_rgba(34,211,238,0.65)]',
          badge: 'bg-cyan-500/25 text-cyan-200 border-cyan-400/50',
          icon: <MousePointerClick className="w-4 h-4 text-cyan-300" />,
          accent: '#22d3ee',
        }
      : currentStep.category === 'parameter'
      ? {
          ring: 'border-amber-400 shadow-[0_0_35px_rgba(251,191,36,0.65)]',
          badge: 'bg-amber-500/25 text-amber-200 border-amber-400/50',
          icon: <Sliders className="w-4 h-4 text-amber-300" />,
          accent: '#fbbf24',
        }
      : {
          ring: 'border-emerald-400 shadow-[0_0_35px_rgba(52,211,153,0.65)]',
          badge: 'bg-emerald-500/25 text-emerald-200 border-emerald-400/50',
          icon: <Eye className="w-4 h-4 text-emerald-300" />,
          accent: '#34d399',
        };

  const sceneLabels: { key: TourSceneKey; label: string }[] = [
    { key: 'xrd-step-1', label: 'Step 1: 前処理' },
    { key: 'xrd-step-2', label: 'Step 2: 初期値' },
    { key: 'xrd-step-3', label: 'Step 3: 連続解析' },
    { key: 'xrd-step-4', label: 'Step 4: 修復・出力' },
    { key: 'xrd-step-5', label: 'Step 5: 物理グラフ' },
    { key: 'dic-mode', label: 'DIC 動画抽出' },
  ];

  return (
    <div
      className="fixed inset-0 z-[9999] pointer-events-auto select-none"
      role="dialog"
      aria-modal="true"
      aria-label="アニメーション付きインタラクティブ操作ガイド"
    >
      {/* Dimmed Backdrop with Spotlight Cutout */}
      <svg
        className="fixed inset-0 w-full h-full pointer-events-auto"
        onClick={onClose}
      >
        <defs>
          <mask id="xrd-tour-spotlight-mask">
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            {targetRect && (
              <rect
                x={targetRect.left}
                y={targetRect.top}
                width={targetRect.width}
                height={targetRect.height}
                rx="14"
                ry="14"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          x="0"
          y="0"
          width="100%"
          height="100%"
          fill="rgba(5, 8, 15, 0.78)"
          mask="url(#xrd-tour-spotlight-mask)"
        />
      </svg>

      {/* Highlighted Target Pulsing Spotlight Frame + Animated Pointer Hand */}
      {targetRect && (
        <>
          <div
            className={`fixed rounded-2xl border-2 pointer-events-none transition-all duration-300 ease-out ${categoryColor.ring}`}
            style={{
              top: targetRect.top,
              left: targetRect.left,
              width: targetRect.width,
              height: targetRect.height,
            }}
          >
            {/* Outer expanding pulse ring */}
            <div
              className="absolute -inset-2 rounded-2xl border-2 opacity-60 animate-ping pointer-events-none"
              style={{ borderColor: categoryColor.accent, animationDuration: '1.8s' }}
            />
            {/* Corner target brackets */}
            <div
              className="absolute -top-1.5 -left-1.5 w-4 h-4 border-t-4 border-l-4 rounded-tl"
              style={{ borderColor: categoryColor.accent }}
            />
            <div
              className="absolute -top-1.5 -right-1.5 w-4 h-4 border-t-4 border-r-4 rounded-tr"
              style={{ borderColor: categoryColor.accent }}
            />
            <div
              className="absolute -bottom-1.5 -left-1.5 w-4 h-4 border-b-4 border-l-4 rounded-bl"
              style={{ borderColor: categoryColor.accent }}
            />
            <div
              className="absolute -bottom-1.5 -right-1.5 w-4 h-4 border-b-4 border-r-4 rounded-br"
              style={{ borderColor: categoryColor.accent }}
            />
          </div>

          {/* Animated Bouncing Pointer Badge right on the target edge */}
          <div
            className="fixed z-[10000] pointer-events-none transition-all duration-300 ease-out flex items-center gap-2"
            style={{
              top: Math.max(8, targetRect.top - 38),
              left: Math.min(viewport.w - 220, Math.max(12, targetRect.left + 12)),
            }}
          >
            <div
              className="px-3 py-1 rounded-full text-xs font-extrabold tracking-wide shadow-xl flex items-center gap-1.5 animate-bounce"
              style={{
                backgroundColor: categoryColor.accent,
                color: '#090d16',
                animationDuration: '1.15s',
              }}
            >
              <span>👇 ここを操作・確認！</span>
            </div>
          </div>
        </>
      )}

      {/* Floating Coachmark Card */}
      <div
        className="fixed z-[10001] rounded-2xl bg-zinc-900/95 backdrop-blur-xl border-2 border-zinc-700/90 shadow-[0_24px_70px_rgba(0,0,0,0.85)] p-5 transition-all duration-300 ease-out"
        style={{
          width: cardWidth,
          top: cardTop,
          left: cardLeft,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Directional Arrow Connector */}
        {targetRect && pointerPlacement === 'top' && (
          <div
            className="absolute -top-3 w-5 h-5 rotate-45 bg-zinc-900 border-t-2 border-l-2 border-zinc-700"
            style={{
              left: Math.min(
                cardWidth - 36,
                Math.max(24, targetRect.left + targetRect.width / 2 - cardLeft)
              ),
            }}
          />
        )}
        {targetRect && pointerPlacement === 'bottom' && (
          <div
            className="absolute -bottom-3 w-5 h-5 rotate-45 bg-zinc-900 border-b-2 border-r-2 border-zinc-700"
            style={{
              left: Math.min(
                cardWidth - 36,
                Math.max(24, targetRect.left + targetRect.width / 2 - cardLeft)
              ),
            }}
          />
        )}

        {/* Scene Switcher Bar */}
        {onSwitchScene && (
          <div className="flex items-center gap-1 overflow-x-auto pb-2.5 mb-3 border-b border-zinc-800">
            <Compass className="w-3.5 h-3.5 text-cyan-400 shrink-0 mr-1" />
            {sceneLabels.map((sc) => (
              <button
                key={sc.key}
                type="button"
                onClick={() => onSwitchScene(sc.key)}
                className={`px-2 py-1 rounded-md text-[11px] font-bold whitespace-nowrap transition-colors ${
                  sc.key === sceneKey
                    ? 'bg-cyan-500/25 text-cyan-200 border border-cyan-500/40'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                }`}
              >
                {sc.label}
              </button>
            ))}
          </div>
        )}

        {/* Top Row: Category Badge + Step Indicator + Close */}
        <div className="flex items-center justify-between gap-2 mb-2.5">
          <div className="flex items-center gap-2">
            <span
              className={`px-2.5 py-1 rounded-lg text-xs font-bold border flex items-center gap-1.5 ${categoryColor.badge}`}
            >
              {categoryColor.icon}
              <span>{currentStep.badgeText}</span>
            </span>
            <span className="text-xs font-mono font-bold text-zinc-400">
              Step {currentStepIdx + 1} / {steps.length}
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
            title="ガイドを閉じる (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Title & Description */}
        <h3 className="text-base sm:text-lg font-extrabold text-zinc-100 leading-snug mb-2">
          {currentStep.title}
        </h3>
        <p className="text-sm text-zinc-200 leading-relaxed mb-2.5">
          {currentStep.description}
        </p>

        {currentStep.subHint && (
          <div className="rounded-xl bg-zinc-950/90 border border-zinc-800 px-3.5 py-2 text-xs text-zinc-300 leading-relaxed mb-3 flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>{currentStep.subHint}</span>
          </div>
        )}

        {!targetRect && (
          <div className="rounded-xl bg-amber-950/40 border border-amber-500/30 px-3.5 py-2 text-xs text-amber-200 mb-3 flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              ※ このボタン・パネルは前段階の処理実行後または該当サブタブ選択時に画面へ表示されます。
            </span>
          </div>
        )}

        {/* Interactive Auto-Click Action Button if applicable */}
        {currentStep.allowAutoClick && targetRect && (
          <button
            type="button"
            onClick={handleAutoClickTarget}
            className="w-full mb-3 py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-zinc-950 font-extrabold text-sm shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2 transition-all"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>{currentStep.autoClickLabel || 'このボタンを実際に押して次へ進む'}</span>
          </button>
        )}

        {/* Step Progress Dots & Navigation Controls */}
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-zinc-800">
          <div className="flex items-center gap-1.5">
            {steps.map((st, idx) => (
              <button
                key={st.id}
                type="button"
                onClick={() => setCurrentStepIdx(idx)}
                className={`h-2 rounded-full transition-all ${
                  idx === currentStepIdx
                    ? 'w-6 bg-cyan-400'
                    : 'w-2 bg-zinc-700 hover:bg-zinc-500'
                }`}
                title={st.title}
              />
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCurrentStepIdx((prev) => Math.max(0, prev - 1))}
              disabled={currentStepIdx === 0}
              className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-xs font-bold text-zinc-200 flex items-center gap-1 transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>前へ</span>
            </button>

            {currentStepIdx < steps.length - 1 ? (
              <button
                type="button"
                onClick={() => setCurrentStepIdx((prev) => Math.min(steps.length - 1, prev + 1))}
                className="px-3.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-xs font-extrabold text-zinc-950 flex items-center gap-1 transition-colors"
              >
                <span>次の場所を案内</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-xs font-extrabold text-zinc-950 flex items-center gap-1.5 transition-colors"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>ガイド完了</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
