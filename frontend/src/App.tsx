import React, { useState, useEffect, useMemo } from 'react';
import {
  Activity,
  Film,
  FolderSearch,
  Crosshair,
  PlayCircle,
  Table2,
  CheckCircle2,
  TrendingUp,
  PanelLeftClose,
  PanelLeftOpen,
  Terminal,
  Compass,
  FileSpreadsheet,
  FolderOpen,
  Layers,
  Sparkles,
  Sliders,
  Eye,
  MousePointerClick,
  ChevronRight,
  ChevronDown,
  Cpu,
  ShieldCheck,
  BookOpen,
  X,
} from 'lucide-react';
import type {
  PreprocessRunResponse,
  InitialAutoDetectResponse,
  GroupBatchConfig,
  BatchGroupResult,
} from './types/xrd';
import { Step1Preprocess } from './components/Step1Preprocess';
import { Step2InitialPick } from './components/Step2InitialPick';
import { Step3BatchRun } from './components/Step3BatchRun';
import { Step4ReviewExport } from './components/Step4ReviewExport';
import { Step5PhysicsAnalysis } from './components/Step5PhysicsAnalysis';
import { VideoUtilityTab } from './components/VideoUtilityTab';
import {
  InteractiveTourOverlay,
  TourSceneKey,
  TOUR_STEPS_BY_SCENE,
} from './components/InteractiveTourOverlay';

type MainMode = 'xrd' | 'dic';
type XrdStep = 1 | 2 | 3 | 4 | 5;

interface LogEntry {
  time: string;
  level: 'INFO' | 'SUCCESS' | 'GUIDE';
  message: string;
}

const nowTimeStr = (): string => {
  const d = new Date();
  return d.toTimeString().split(' ')[0];
};

export const App: React.FC = () => {
  const [mainMode, setMainMode] = useState<MainMode>('xrd');
  const [xrdStep, setXrdStep] = useState<XrdStep>(1);

  // IDE Workspace Dock States
  const [showSidebar, setShowSidebar] = useState<boolean>(true);
  const [showConsole, setShowConsole] = useState<boolean>(false);
  const [showFormulaModal, setShowFormulaModal] = useState<boolean>(false);
  const [openMenu, setOpenMenu] = useState<'file' | 'stage' | 'view' | 'guide' | null>(null);

  // Interactive Animated Spotlight Tour State
  const [tourOpen, setTourOpen] = useState<boolean>(false);
  const [tourInitialStep, setTourInitialStep] = useState<number>(0);

  // Shared XRD Pipeline State
  const [folderPath, setFolderPath] = useState<string>('sample_data/Seki_age_2_tensile');
  const [specimenName, setSpecimenName] = useState<string>('Seki_age_2_tensile');
  const [preprocessResult, setPreprocessResult] = useState<PreprocessRunResponse | null>(null);
  const [initialData, setInitialData] = useState<InitialAutoDetectResponse | null>(null);
  const [batchConfigs, setBatchConfigs] = useState<GroupBatchConfig[]>([]);
  const [initialExcelPath, setInitialExcelPath] = useState<string>('');
  const [batchResults, setBatchResults] = useState<Record<string, BatchGroupResult>>({});

  const candidateGroups = useMemo(() => initialData?.candidate_groups ?? [], [initialData]);
  const dimtOnsetNum = useMemo(
    () => initialData?.dimt_onset_estimate ?? 200,
    [initialData]
  );

  // IDE Session Logs
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      time: nowTimeStr(),
      level: 'INFO',
      message:
        'XRD AutoFit Studio & DIC Workbench 起動完了 — Origin70 互換 Voigt エンジン (wG/wL 独立最適化・Seed=42・bcc211 物理拘束対応)',
    },
  ]);

  const appendLog = (level: LogEntry['level'], message: string) => {
    setLogs((prev) => [...prev.slice(-49), { time: nowTimeStr(), level, message }]);
  };

  // Current scene key for the interactive tour
  const currentSceneKey: TourSceneKey = useMemo(() => {
    if (mainMode === 'dic') return 'dic-mode';
    return `xrd-step-${xrdStep}` as TourSceneKey;
  }, [mainMode, xrdStep]);

  // Listen for custom tour start events from TutorialGuideBanner or child components
  useEffect(() => {
    const handleStartTourEvent = (ev: Event) => {
      const customEv = ev as CustomEvent<{ stepIndex?: number }>;
      const idx = customEv.detail?.stepIndex ?? 0;
      setTourInitialStep(idx);
      setTourOpen(true);
    };
    window.addEventListener('xrd-start-tour', handleStartTourEvent);
    return () => window.removeEventListener('xrd-start-tour', handleStartTourEvent);
  }, []);

  // Close top dropdown menus when clicking outside
  useEffect(() => {
    if (!openMenu) return;
    const close = () => setOpenMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [openMenu]);

  const startTourAtCategory = (category: 'button' | 'parameter' | 'detail' | 'all') => {
    const sceneSteps = TOUR_STEPS_BY_SCENE[currentSceneKey] || [];
    if (category === 'all') {
      setTourInitialStep(0);
    } else {
      const foundIdx = sceneSteps.findIndex((s) => s.category === category);
      setTourInitialStep(foundIdx >= 0 ? foundIdx : 0);
    }
    setTourOpen(true);
    appendLog('GUIDE', `アニメーション操作ガイド (${currentSceneKey}) を開始しました。`);
  };

  const handleTourSwitchScene = (scene: TourSceneKey) => {
    if (scene === 'dic-mode') {
      setMainMode('dic');
    } else {
      setMainMode('xrd');
      const num = Number(scene.replace('xrd-step-', '')) as XrdStep;
      if (num >= 1 && num <= 5) setXrdStep(num);
    }
    setTourInitialStep(0);
  };

  const stepsMeta: {
    step: XrdStep;
    tabFile: string;
    title: string;
    subtitle: string;
    icon: React.ReactNode;
    done: boolean;
  }[] = [
    {
      step: 1,
      tabFile: '01_Preprocess.xrd',
      title: 'Step 1: フォルダ選択・BG除去',
      subtitle: '.tth自動仕分け＆ベースライン除去',
      icon: <FolderSearch className="w-4 h-4" />,
      done: !!preprocessResult,
    },
    {
      step: 2,
      tabFile: '02_InitialPick.voigt',
      title: 'Step 2: 初期値探索・相選択',
      subtitle: '複数ファイルVoigt初期値＆_initial.xlsx',
      icon: <Crosshair className="w-4 h-4" />,
      done: candidateGroups.some((g) => g.selected) && !!initialExcelPath,
    },
    {
      step: 3,
      tabFile: '03_BatchFit.run',
      title: 'Step 3: 全ファイル連続解析',
      subtitle: 'bcc211物理拘束＆連続最小二乗フィット',
      icon: <PlayCircle className="w-4 h-4" />,
      done: Object.keys(batchResults).length > 0,
    },
    {
      step: 4,
      tabFile: '04_OutlierRepair.xlsx',
      title: 'Step 4: 要確認一括修復・Excel出力',
      subtitle: '相別一括選択・再フィット＆output.xlsx',
      icon: <Table2 className="w-4 h-4" />,
      done: Object.keys(batchResults).length > 0,
    },
    {
      step: 5,
      tabFile: '05_PhysicsPlot.mat',
      title: 'Step 5: 相分率・転位密度グラフ',
      subtitle: 'マルテンサイト分率・転位密度・格子ひずみ',
      icon: <TrendingUp className="w-4 h-4" />,
      done: false,
    },
  ];

  const totalOutlierCount = useMemo(() => {
    return Object.values(batchResults).reduce(
      (acc, g) => acc + (g.outlier_nums?.length || 0),
      0
    );
  }, [batchResults]);

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#090d16] text-zinc-100 flex flex-col select-none">
      {/* =====================================================================
          ZONE 1: TOP SCIENTIFIC IDE MENU BAR & COMMAND RIBBON
         ===================================================================== */}
      <header className="h-12 shrink-0 bg-[#0d1322] border-b border-zinc-800/90 px-3 flex items-center justify-between gap-3 z-40">
        {/* Left: Brand Identity + Desktop Menus */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2.5 pr-2 border-r border-zinc-800">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500/30 to-blue-600/30 border border-cyan-400/50 flex items-center justify-center shadow-inner">
              <Activity className="w-4 h-4 text-cyan-300" />
            </div>
            <div className="leading-tight">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-extrabold tracking-tight text-zinc-100">
                  XRD AutoFit Studio
                </span>
                <span className="px-1.5 py-0.5 rounded bg-cyan-500/20 border border-cyan-500/40 text-[10px] font-mono font-bold text-cyan-300">
                  PRO WORKBENCH
                </span>
              </div>
              <div className="text-[10px] font-mono text-zinc-400 hidden xl:block">
                SPring-8 In-situ Diffraction &amp; DIC Analysis IDE
              </div>
            </div>
          </div>

          {/* Native-Style Menu Strip */}
          <nav className="hidden md:flex items-center gap-1 text-xs font-semibold text-zinc-300 relative">
            {/* FILE MENU */}
            <div className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpenMenu(openMenu === 'file' ? null : 'file');
                }}
                className="px-2.5 py-1.5 rounded-md hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                ファイル(F)
              </button>
              {openMenu === 'file' && (
                <div className="absolute left-0 top-full mt-1 w-64 rounded-xl bg-zinc-900 border border-zinc-700 shadow-2xl py-1.5 z-50 text-xs">
                  <button
                    type="button"
                    onClick={() => {
                      setMainMode('xrd');
                      setXrdStep(1);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 flex items-center justify-between"
                  >
                    <span>測定データフォルダを開く...</span>
                    <span className="font-mono text-zinc-400">Step 1</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMainMode('xrd');
                      setXrdStep(4);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 flex items-center justify-between"
                  >
                    <span>解析結果 output.xlsx 保存画面へ</span>
                    <span className="font-mono text-zinc-400">Step 4</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setMainMode('xrd');
                      setXrdStep(5);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 flex items-center justify-between"
                  >
                    <span>既存の output.xlsx から物理グラフ作成</span>
                    <span className="font-mono text-zinc-400">Step 5</span>
                  </button>
                  <div className="my-1 border-t border-zinc-800" />
                  <button
                    type="button"
                    onClick={() => {
                      setMainMode('dic');
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 text-amber-300 flex items-center justify-between"
                  >
                    <span>DIC 動画フレーム抽出ツールへ切替</span>
                    <span className="font-mono">CV2</span>
                  </button>
                </div>
              )}
            </div>

            {/* STAGE MENU */}
            <div className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpenMenu(openMenu === 'stage' ? null : 'stage');
                }}
                className="px-2.5 py-1.5 rounded-md hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                解析ステージ(A)
              </button>
              {openMenu === 'stage' && (
                <div className="absolute left-0 top-full mt-1 w-72 rounded-xl bg-zinc-900 border border-zinc-700 shadow-2xl py-1.5 z-50 text-xs">
                  {stepsMeta.map((s) => (
                    <button
                      key={s.step}
                      type="button"
                      onClick={() => {
                        setMainMode('xrd');
                        setXrdStep(s.step);
                        setOpenMenu(null);
                      }}
                      className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 flex items-center justify-between"
                    >
                      <span className="font-bold text-zinc-100">{s.title}</span>
                      {s.done && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* VIEW / DOCK MENU */}
            <div className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpenMenu(openMenu === 'view' ? null : 'view');
                }}
                className="px-2.5 py-1.5 rounded-md hover:bg-zinc-800 hover:text-zinc-100 transition-colors"
              >
                表示・ドック(V)
              </button>
              {openMenu === 'view' && (
                <div className="absolute left-0 top-full mt-1 w-64 rounded-xl bg-zinc-900 border border-zinc-700 shadow-2xl py-1.5 z-50 text-xs">
                  <button
                    type="button"
                    onClick={() => {
                      setShowSidebar((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 flex items-center justify-between"
                  >
                    <span>左プロジェクト・シートツリー</span>
                    <span className="font-mono text-cyan-400">{showSidebar ? 'ON' : 'OFF'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowConsole((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 flex items-center justify-between"
                  >
                    <span>下部システム実行ログコンソール</span>
                    <span className="font-mono text-cyan-400">{showConsole ? 'ON' : 'OFF'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowFormulaModal(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 flex items-center justify-between"
                  >
                    <span>物理モデル・拘束条件リファレンス</span>
                    <span className="font-mono text-amber-400">表示</span>
                  </button>
                </div>
              )}
            </div>

            {/* GUIDE MENU */}
            <div className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setOpenMenu(openMenu === 'guide' ? null : 'guide');
                }}
                className="px-2.5 py-1.5 rounded-md hover:bg-zinc-800 text-cyan-300 font-bold transition-colors"
              >
                操作ガイド(G)
              </button>
              {openMenu === 'guide' && (
                <div className="absolute left-0 top-full mt-1 w-72 rounded-xl bg-zinc-900 border border-zinc-700 shadow-2xl py-1.5 z-50 text-xs">
                  <button
                    type="button"
                    onClick={() => {
                      startTourAtCategory('all');
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2.5 text-left hover:bg-zinc-800 text-cyan-300 font-bold flex items-center gap-2"
                  >
                    <MousePointerClick className="w-4 h-4" />
                    <span>現在の画面のアニメーションガイドを開始</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      startTourAtCategory('parameter');
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 text-amber-300 flex items-center gap-2"
                  >
                    <Sliders className="w-4 h-4" />
                    <span>パラメータ調節場所をピンポイント案内</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      startTourAtCategory('detail');
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left hover:bg-zinc-800 text-emerald-300 flex items-center gap-2"
                  >
                    <Eye className="w-4 h-4" />
                    <span>詳細波形・グラフ確認場所を案内</span>
                  </button>
                </div>
              )}
            </div>
          </nav>
        </div>

        {/* Right: Prominent Animated Tour Trigger + Mode Switcher */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => startTourAtCategory('all')}
            className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-zinc-950 font-extrabold text-xs sm:text-sm flex items-center gap-1.5 shadow-lg shadow-cyan-500/20 transition-all"
            title="どこのボタンを押せばいいか・どこでパラメータ調節できるかをスポットライトとアニメーションで案内します"
          >
            <MousePointerClick className="w-4 h-4" />
            <span>アニメーション操作ガイド</span>
          </button>

          <button
            type="button"
            onClick={() => setShowFormulaModal(true)}
            className="hidden sm:flex px-3 py-1.5 rounded-lg bg-zinc-800/90 hover:bg-zinc-700 border border-zinc-700 text-xs font-bold text-zinc-200 items-center gap-1.5 transition-colors"
            title="物理拘束・Voigt関数・転位密度算出式の仕様を確認"
          >
            <BookOpen className="w-3.5 h-3.5 text-amber-400" />
            <span>解析モデル仕様</span>
          </button>

          {/* Workbench Mode Switcher */}
          <div className="flex items-center bg-[#070a12] p-1 rounded-lg border border-zinc-800">
            <button
              type="button"
              onClick={() => setMainMode('xrd')}
              className={`px-3 py-1 rounded-md text-xs font-bold flex items-center gap-1.5 transition-all ${
                mainMode === 'xrd'
                  ? 'bg-cyan-500 text-zinc-950 shadow'
                  : 'text-zinc-400 hover:text-zinc-100'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>XRD 解析</span>
            </button>
            <button
              type="button"
              onClick={() => setMainMode('dic')}
              className={`px-3 py-1 rounded-md text-xs font-bold flex items-center gap-1.5 transition-all ${
                mainMode === 'dic'
                  ? 'bg-amber-500 text-zinc-950 shadow'
                  : 'text-zinc-400 hover:text-zinc-100'
              }`}
            >
              <Film className="w-3.5 h-3.5" />
              <span>DIC 動画抽出</span>
            </button>
          </div>
        </div>
      </header>

      {/* =====================================================================
          MAIN IDE BODY: LEFT ACTIVITY BAR + PROJECT SIDEBAR + WORKBENCH
         ===================================================================== */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* ZONE 2: VS Code / Spyder Style Left Activity Icon Rail */}
        <aside className="w-12 shrink-0 bg-[#0b101d] border-r border-zinc-800/90 flex flex-col items-center justify-between py-2.5 z-30">
          <div className="flex flex-col items-center gap-2">
            {/* XRD Mode Icon */}
            <button
              type="button"
              onClick={() => setMainMode('xrd')}
              className={`relative w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
                mainMode === 'xrd'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/70'
              }`}
              title="In-situ XRD 全自動解析スタジオ"
            >
              {mainMode === 'xrd' && (
                <span className="absolute -left-1.5 top-1.5 bottom-1.5 w-1 rounded-r bg-cyan-400" />
              )}
              <Activity className="w-5 h-5" />
            </button>

            {/* DIC Mode Icon */}
            <button
              type="button"
              onClick={() => setMainMode('dic')}
              className={`relative w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
                mainMode === 'dic'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/70'
              }`}
              title="DIC用 動画フレーム高速切り出しツール"
            >
              {mainMode === 'dic' && (
                <span className="absolute -left-1.5 top-1.5 bottom-1.5 w-1 rounded-r bg-amber-400" />
              )}
              <Film className="w-5 h-5" />
            </button>

            <div className="w-6 border-t border-zinc-800 my-1" />

            {/* Toggle Project Explorer Sidebar */}
            <button
              type="button"
              onClick={() => setShowSidebar((prev) => !prev)}
              className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
                showSidebar
                  ? 'bg-zinc-800 text-cyan-300'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/70'
              }`}
              title="プロジェクト・シートエクスプローラーを開閉"
            >
              {showSidebar ? (
                <PanelLeftClose className="w-5 h-5" />
              ) : (
                <PanelLeftOpen className="w-5 h-5" />
              )}
            </button>

            {/* Toggle Bottom Log Console */}
            <button
              type="button"
              onClick={() => setShowConsole((prev) => !prev)}
              className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all ${
                showConsole
                  ? 'bg-zinc-800 text-emerald-300'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/70'
              }`}
              title="システム実行ログ・コンソールを開閉"
            >
              <Terminal className="w-5 h-5" />
            </button>
          </div>

          <div className="flex flex-col items-center gap-2">
            {/* Launch Interactive Spotlight Tour */}
            <button
              type="button"
              onClick={() => startTourAtCategory('all')}
              className="w-9 h-9 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-300 flex items-center justify-center transition-all"
              title="アニメーション操作ガイドを起動"
            >
              <Compass className="w-5 h-5" />
            </button>
          </div>
        </aside>

        {/* ZONE 3: Collapsible OriginPro / Spyder Style Project & Sheet Explorer Sidebar */}
        {showSidebar && (
          <aside className="w-64 shrink-0 bg-[#0d1322] border-r border-zinc-800/90 flex flex-col justify-between overflow-y-auto z-20">
            <div className="p-3 space-y-4">
              {/* Explorer Header */}
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                <span className="text-[11px] font-mono font-extrabold tracking-wider text-zinc-400 uppercase">
                  PROJECT &amp; SHEET EXPLORER
                </span>
                <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-[10px] font-mono text-cyan-300">
                  Origin70互換
                </span>
              </div>

              {/* Active Specimen Workspace Box */}
              <div className="rounded-xl bg-zinc-950/90 border border-zinc-800/90 p-3 space-y-2">
                <div className="flex items-center gap-2 text-xs font-bold text-cyan-300">
                  <FolderOpen className="w-4 h-4 shrink-0" />
                  <span className="truncate">{specimenName || '未選択'}</span>
                </div>
                <div className="text-[11px] font-mono text-zinc-400 break-all line-clamp-2">
                  {folderPath || 'フォルダ未選択 (Step 1 で選択)'}
                </div>
                <div className="grid grid-cols-2 gap-1.5 pt-1 text-[11px] font-mono">
                  <div className="bg-zinc-900 rounded px-2 py-1 border border-zinc-800">
                    <span className="text-zinc-400">Files: </span>
                    <strong className="text-zinc-100">
                      {preprocessResult ? preprocessResult.nums.length : 0}
                    </strong>
                  </div>
                  <div className="bg-zinc-900 rounded px-2 py-1 border border-zinc-800">
                    <span className="text-zinc-400">DIMT: </span>
                    <strong className="text-amber-300">#{dimtOnsetNum}</strong>
                  </div>
                </div>
              </div>

              {/* Pipeline Workflow Tree */}
              <div className="space-y-1">
                <div className="text-[11px] font-mono font-bold text-zinc-400 px-1 mb-1.5 flex items-center gap-1">
                  <ChevronDown className="w-3.5 h-3.5" />
                  <span>WORKFLOW PIPELINE</span>
                </div>
                {stepsMeta.map((item) => {
                  const active = mainMode === 'xrd' && xrdStep === item.step;
                  return (
                    <button
                      key={item.step}
                      type="button"
                      onClick={() => {
                        setMainMode('xrd');
                        setXrdStep(item.step);
                      }}
                      className={`w-full px-2.5 py-2 rounded-lg text-left transition-all flex items-center justify-between gap-2 ${
                        active
                          ? 'bg-cyan-500/20 border border-cyan-500/50 text-cyan-200 font-bold'
                          : 'hover:bg-zinc-800/70 text-zinc-300 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={active ? 'text-cyan-300' : 'text-zinc-400'}>
                          {item.icon}
                        </span>
                        <div className="truncate">
                          <div className="text-xs truncate">{item.title}</div>
                          <div className="text-[10px] font-mono text-zinc-400 truncate">
                            {item.tabFile}
                          </div>
                        </div>
                      </div>
                      {item.done ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 text-zinc-600 shrink-0" />
                      )}
                    </button>
                  );
                })}

                <button
                  type="button"
                  onClick={() => setMainMode('dic')}
                  className={`w-full px-2.5 py-2 rounded-lg text-left transition-all flex items-center justify-between gap-2 mt-1 ${
                    mainMode === 'dic'
                      ? 'bg-amber-500/20 border border-amber-500/50 text-amber-200 font-bold'
                      : 'hover:bg-zinc-800/70 text-zinc-300 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Film className="w-4 h-4 text-amber-400 shrink-0" />
                    <div className="truncate">
                      <div className="text-xs truncate">DIC 動画フレーム抽出</div>
                      <div className="text-[10px] font-mono text-zinc-400 truncate">
                        DIC_FrameExtractor.cv2
                      </div>
                    </div>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-zinc-600 shrink-0" />
                </button>
              </div>

              {/* Active Peak Sheets (Origin Workbook Style) */}
              <div className="space-y-1.5 pt-2 border-t border-zinc-800">
                <div className="text-[11px] font-mono font-bold text-zinc-400 px-1 flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5 text-cyan-400" />
                    <span>PEAK SHEETS (結晶面)</span>
                  </span>
                  <span>{candidateGroups.filter((g) => g.selected).length} 選択</span>
                </div>

                {candidateGroups.length === 0 ? (
                  <div className="text-xs text-zinc-500 px-2 py-2 bg-zinc-950/50 rounded-lg border border-zinc-800/60">
                    Step 2 で初期値探索を実行すると全結晶面シートがここに一覧表示されます
                  </div>
                ) : (
                  <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                    {candidateGroups
                      .filter((g) => g.selected)
                      .map((grp) => {
                        const fitRes = batchResults[grp.group_id];
                        const outliers = fitRes?.outlier_nums?.length || 0;
                        return (
                          <button
                            key={grp.group_id}
                            type="button"
                            onClick={() => {
                              setMainMode('xrd');
                              setXrdStep(fitRes ? 4 : 2);
                            }}
                            className="w-full px-2.5 py-1.5 rounded-lg bg-zinc-950/80 hover:bg-zinc-800 border border-zinc-800 text-left flex items-center justify-between text-xs transition-colors"
                          >
                            <span className="font-mono font-bold text-zinc-200 truncate">
                              {grp.peaks.join(' + ')}
                            </span>
                            {fitRes ? (
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                                  outliers > 0
                                    ? 'bg-amber-500/20 text-amber-300'
                                    : 'bg-emerald-500/20 text-emerald-300'
                                }`}
                              >
                                {outliers > 0 ? `要確認:${outliers}` : 'OK'}
                              </span>
                            ) : (
                              <span className="text-[10px] font-mono text-cyan-400">
                                #{grp.selected_num}
                              </span>
                            )}
                          </button>
                        );
                      })}
                  </div>
                )}
              </div>

              {/* Excel Output Artifacts */}
              <div className="space-y-1.5 pt-2 border-t border-zinc-800">
                <div className="text-[11px] font-mono font-bold text-zinc-400 px-1 flex items-center gap-1">
                  <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
                  <span>EXCEL ARTIFACTS</span>
                </div>
                <div className="rounded-lg bg-zinc-950/80 border border-zinc-800 p-2.5 space-y-1.5 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-300 truncate">{specimenName}_initial.xlsx</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded ${
                        initialExcelPath
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-zinc-800 text-zinc-500'
                      }`}
                    >
                      {initialExcelPath ? '生成済' : '未生成'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-300 truncate">{specimenName}output.xlsx</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded ${
                        Object.keys(batchResults).length > 0
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-zinc-800 text-zinc-500'
                      }`}
                    >
                      {Object.keys(batchResults).length > 0 ? '出力可' : '待機中'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Quick Interactive Guide Box inside Sidebar */}
            <div className="p-3 border-t border-zinc-800 bg-zinc-950/60 space-y-2">
              <div className="text-xs font-bold text-cyan-300 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>ピンポイント操作案内</span>
              </div>
              <div className="grid grid-cols-1 gap-1.5">
                <button
                  type="button"
                  onClick={() => startTourAtCategory('button')}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/70 border border-cyan-500/40 text-xs font-bold text-cyan-200 flex items-center gap-1.5 transition-colors"
                >
                  <MousePointerClick className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                  <span>次に押すボタンを光らせる</span>
                </button>
                <button
                  type="button"
                  onClick={() => startTourAtCategory('parameter')}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-amber-950/60 hover:bg-amber-900/70 border border-amber-500/40 text-xs font-bold text-amber-200 flex items-center gap-1.5 transition-colors"
                >
                  <Sliders className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>パラメータ調節場所を案内</span>
                </button>
                <button
                  type="button"
                  onClick={() => startTourAtCategory('detail')}
                  className="w-full px-2.5 py-1.5 rounded-lg bg-emerald-950/60 hover:bg-emerald-900/70 border border-emerald-500/40 text-xs font-bold text-emerald-200 flex items-center gap-1.5 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>詳細波形・グラフ確認場所</span>
                </button>
              </div>
            </div>
          </aside>
        )}

        {/* ZONE 4: CENTRAL MULTI-TAB EDITOR & SCIENTIFIC WORKBENCH AREA */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0 bg-[#090d16]">
          {/* VS Code / Spyder Style Document Tab Bar */}
          <div className="h-10 shrink-0 bg-[#0d1322] border-b border-zinc-800 flex items-center justify-between px-2 overflow-x-auto">
            {mainMode === 'xrd' ? (
              <div className="flex items-center gap-1">
                {stepsMeta.map((tab) => {
                  const isCurrent = xrdStep === tab.step;
                  return (
                    <button
                      key={tab.step}
                      type="button"
                      onClick={() => setXrdStep(tab.step)}
                      className={`group relative px-3.5 py-2 rounded-t-lg text-xs font-bold flex items-center gap-2 border-t-2 transition-all whitespace-nowrap ${
                        isCurrent
                          ? 'bg-[#090d16] text-cyan-300 border-t-cyan-400 border-x border-zinc-800'
                          : 'bg-[#0b101d]/60 text-zinc-400 border-t-transparent hover:text-zinc-200 hover:bg-zinc-900/60'
                      }`}
                    >
                      <span className={isCurrent ? 'text-cyan-400' : 'text-zinc-500'}>
                        {tab.icon}
                      </span>
                      <span>{tab.title}</span>
                      {tab.done && (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <div className="px-4 py-2 rounded-t-lg text-xs font-bold flex items-center gap-2 bg-[#090d16] text-amber-300 border-t-2 border-t-amber-400 border-x border-zinc-800">
                  <Film className="w-4 h-4 text-amber-400" />
                  <span>DIC_FrameExtractor.cv2 — 動画フレーム高速一括切り出しワークベンチ</span>
                </div>
              </div>
            )}

            {/* Quick Coachmark Helper Pills on Right of Tab Bar */}
            <div className="hidden lg:flex items-center gap-1.5 pl-2">
              <button
                type="button"
                onClick={() => startTourAtCategory('button')}
                className="px-2.5 py-1 rounded-md bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/30 text-[11px] font-bold text-cyan-300 flex items-center gap-1 transition-colors"
              >
                <MousePointerClick className="w-3 h-3" />
                <span>どこのボタンを押す？</span>
              </button>
              <button
                type="button"
                onClick={() => startTourAtCategory('parameter')}
                className="px-2.5 py-1 rounded-md bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-[11px] font-bold text-amber-300 flex items-center gap-1 transition-colors"
              >
                <Sliders className="w-3 h-3" />
                <span>パラメータ調整はどこ？</span>
              </button>
              <button
                type="button"
                onClick={() => startTourAtCategory('detail')}
                className="px-2.5 py-1 rounded-md bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-[11px] font-bold text-emerald-300 flex items-center gap-1 transition-colors"
              >
                <Eye className="w-3 h-3" />
                <span>詳細確認はどこ？</span>
              </button>
            </div>
          </div>

          {/* Scrollable Central Stage Canvas */}
          <main className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 select-text">
            <div className="max-w-[1560px] mx-auto pb-8">
              {mainMode === 'xrd' ? (
                <>
                  {xrdStep === 1 && (
                    <Step1Preprocess
                      folderPath={folderPath}
                      setFolderPath={setFolderPath}
                      specimenName={specimenName}
                      setSpecimenName={setSpecimenName}
                      preprocessResult={preprocessResult}
                      setPreprocessResult={(res) => {
                        setPreprocessResult(res);
                        appendLog(
                          'SUCCESS',
                          `Step 1 前処理完了: ${res.nums.length} ファイル (${res.background_removal.bcg_dir})`
                        );
                      }}
                      onProceedStep2={() => {
                        setXrdStep(2);
                        appendLog('INFO', 'Step 2 (複数ファイル初期値探索・相選択) へ移動しました。');
                      }}
                    />
                  )}

                  {xrdStep === 2 && (
                    <Step2InitialPick
                      folderPath={folderPath}
                      specimenName={specimenName}
                      initialData={initialData}
                      setInitialData={setInitialData}
                      onConfirmInitialAndProceed={(configs, savedExcelPath) => {
                        setBatchConfigs(configs);
                        setInitialExcelPath(savedExcelPath);
                        setXrdStep(3);
                        appendLog(
                          'SUCCESS',
                          `初期値ファイル保存完了: ${savedExcelPath} (${configs.length} グループ選択)`
                        );
                      }}
                    />
                  )}

                  {xrdStep === 3 && (
                    <Step3BatchRun
                      folderPath={folderPath}
                      specimenName={specimenName}
                      initialExcelPath={initialExcelPath}
                      batchConfigs={batchConfigs}
                      setBatchConfigs={setBatchConfigs}
                      batchResults={batchResults}
                      setBatchResults={setBatchResults}
                      onProceedStep4={() => {
                        setXrdStep(4);
                        appendLog(
                          'SUCCESS',
                          'Step 3 連続Voigtフィッティング完了。Step 4 (要確認フィット修復・Excel出力) へ移動しました。'
                        );
                      }}
                    />
                  )}

                  {xrdStep === 4 && (
                    <Step4ReviewExport
                      folderPath={folderPath}
                      specimenName={specimenName}
                      batchResults={batchResults}
                      setBatchResults={setBatchResults}
                      onProceedStep5={() => {
                        setXrdStep(5);
                        appendLog(
                          'INFO',
                          'Step 5 (マルテンサイト相分率・転位密度・格子ひずみ解析) へ移動しました。'
                        );
                      }}
                    />
                  )}

                  {xrdStep === 5 && (
                    <Step5PhysicsAnalysis
                      folderPath={folderPath}
                      specimenName={specimenName}
                      batchResults={batchResults}
                    />
                  )}
                </>
              ) : (
                <VideoUtilityTab />
              )}
            </div>
          </main>

          {/* ZONE 5-A: Collapsible Bottom Output & Diagnostic Console */}
          {showConsole && (
            <section className="h-44 shrink-0 bg-[#0b101d] border-t border-zinc-800 flex flex-col">
              <div className="px-4 py-1.5 border-b border-zinc-800 flex items-center justify-between text-xs">
                <div className="flex items-center gap-3 font-mono font-bold text-cyan-300">
                  <Terminal className="w-3.5 h-3.5" />
                  <span>SYSTEM EXECUTION &amp; DIAGNOSTIC CONSOLE</span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowConsole(false)}
                  className="text-zinc-400 hover:text-zinc-100"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1 select-text">
                {logs.map((lg, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-zinc-500">[{lg.time}]</span>
                    <span
                      className={
                        lg.level === 'SUCCESS'
                          ? 'text-emerald-400 font-bold'
                          : lg.level === 'GUIDE'
                          ? 'text-amber-300 font-bold'
                          : 'text-cyan-400'
                      }
                    >
                      [{lg.level}]
                    </span>
                    <span className="text-zinc-200">{lg.message}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* =====================================================================
          ZONE 5-B: BOTTOM NATIVE IDE STATUS BAR
         ===================================================================== */}
      <footer className="h-7 shrink-0 bg-[#070b14] border-t border-zinc-800/90 px-3 flex items-center justify-between text-[11px] font-mono text-zinc-400 z-40">
        <div className="flex items-center gap-4 overflow-x-auto">
          <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>READY (Desktop IPC)</span>
          </span>
          <span className="hidden sm:inline flex items-center gap-1 text-zinc-300">
            <Cpu className="w-3 h-3 inline mr-1 text-cyan-400" />
            Engine: Origin70-Voigt (wG/wL Free, Seed=42)
          </span>
          <span className="hidden md:inline text-zinc-400">
            振幅許容: 0.80–1.25x | 幅許容: 0.70–1.40x | bcc211物理拘束: 対応
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span>
            試料: <strong className="text-zinc-200">{specimenName || '未設定'}</strong>
          </span>
          {totalOutlierCount > 0 && (
            <span className="text-amber-300">要確認: {totalOutlierCount}件</span>
          )}
          <button
            type="button"
            onClick={() => setShowConsole((v) => !v)}
            className="hover:text-zinc-100 underline"
          >
            {showConsole ? 'ログを隠す ▼' : '実行ログ ▲'}
          </button>
          <button
            type="button"
            onClick={() => startTourAtCategory('all')}
            className="text-cyan-300 hover:text-cyan-200 font-bold"
          >
            🎯 操作ガイド
          </button>
        </div>
      </footer>

      {/* =====================================================================
          MODAL: PHYSICAL MODEL & CONSTRAINT SPECIFICATION REFERENCE
         ===================================================================== */}
      {showFormulaModal && (
        <div
          className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowFormulaModal(false)}
        >
          <div
            className="max-w-3xl w-full rounded-2xl bg-zinc-900 border border-zinc-700 shadow-2xl p-6 space-y-4 select-text"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2.5">
                <BookOpen className="w-5 h-5 text-cyan-400" />
                <h3 className="text-lg font-extrabold text-zinc-100">
                  Origin完全互換 Voigt 解析エンジン ＆ 物理拘束モデル仕様
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowFormulaModal(false)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 text-xs sm:text-sm text-zinc-300">
              <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
                <div className="font-bold text-cyan-300">
                  1. ガウス幅 wG・ローレンツ幅 wL の完全独立最適化
                </div>
                <p className="leading-relaxed">
                  lmfit のデフォルト拘束（gamma = sigma）を解除し、全ステップで{' '}
                  <code className="text-cyan-200">vary=True, expr=None</code>{' '}
                  を明示。Olivero-Longbothum 式で Origin70 互換の合成半値幅 FWHM を算出します。
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
                <div className="font-bold text-amber-300">
                  2. 独立ピーク bcc211 からの Bragg 幾何学拘束
                </div>
                <p className="leading-relaxed">
                  孤立ピーク <code className="text-amber-200">bcc211</code> の中心角度と FWHM から{' '}
                  <code className="text-amber-200">
                    θ_110 = arcsin(sin(θ_211) / √3)
                  </code>{' '}
                  および <code className="text-amber-200">tan(θ_110)/tan(θ_211)</code>{' '}
                  比を用いて重畳ピーク <code className="text-amber-200">bcc110</code> を物理ガイドします。
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
                <div className="font-bold text-emerald-300">
                  3. 局所直線バックグラウンド減算 ＆ 乱数シード固定
                </div>
                <p className="leading-relaxed">
                  各ピーク切り出し範囲の両端10点平均を結ぶ局所直線BGを差し引き、浮き上がりを防止。また{' '}
                  <code className="text-emerald-200">random.seed(42)</code>{' '}
                  により100%の再現性を保証します。
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 space-y-1.5">
                <div className="font-bold text-purple-300">
                  4. マルテンサイト相分率 ＆ Modified Williamson-Hall 転位密度
                </div>
                <p className="leading-relaxed">
                  結晶構造因子補正済みの積分強度比から相分率 <code className="text-purple-200">f_α&apos;</code>{' '}
                  を算出し、FWHM と面指数別コントラスト因子から転位密度{' '}
                  <code className="text-purple-200">ρ_γ, ρ_α&apos;</code> を自動計算します。
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          INTERACTIVE ANIMATED SPOTLIGHT & POINTER TOUR OVERLAY
         ===================================================================== */}
      <InteractiveTourOverlay
        sceneKey={currentSceneKey}
        isOpen={tourOpen}
        initialStepIndex={tourInitialStep}
        onClose={() => setTourOpen(false)}
        onSwitchScene={handleTourSwitchScene}
      />
    </div>
  );
};

export default App;
