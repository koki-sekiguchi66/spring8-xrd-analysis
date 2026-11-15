import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Command,
  FileSpreadsheet,
  Film,
  Folder,
  HelpCircle,
  Layers,
  PanelBottom,
  PanelLeft,
  PlayCircle,
  Search,
  Terminal,
} from 'lucide-react';
import {
  BatchGroupResult,
  GroupBatchConfig,
  InitialAutoDetectResponse,
  PreprocessRunResponse,
} from './types/xrd';
import { apiGet, apiPost, cn, isDesktopBridge } from './lib/utils';
import { ModelSpecModal } from './components/ModelSpecModal';
import { Step1Preprocess } from './components/Step1Preprocess';
import { Step2InitialPick } from './components/Step2InitialPick';
import { Step3BatchRun } from './components/Step3BatchRun';
import { Step4ReviewExport } from './components/Step4ReviewExport';
import { Step5PhysicsAnalysis } from './components/Step5PhysicsAnalysis';
import { VideoUtilityTab } from './components/VideoUtilityTab';
import { CommandItem, CommandPalette } from './components/ui/CommandPalette';
import { SegmentedControl } from './components/ui/SegmentedControl';
import { StatusBadge } from './components/ui/StatusBadge';

type MainMode = 'xrd' | 'dic';
type XrdStep = 1 | 2 | 3 | 4 | 5;

interface LogEntry {
  id: number;
  time: string;
  level: 'info' | 'warn' | 'error';
  message: string;
}

export const App: React.FC = () => {
  const [mainMode, setMainMode] = useState<MainMode>('xrd');
  const [xrdStep, setXrdStep] = useState<XrdStep>(1);

  const [showSidebar, setShowSidebar] = useState<boolean>(true);
  const [showConsole, setShowConsole] = useState<boolean>(false);
  const [showSpecModal, setShowSpecModal] = useState<boolean>(false);
  const [showPalette, setShowPalette] = useState<boolean>(false);
  const [openMenu, setOpenMenu] = useState<'file' | 'view' | 'help' | null>(null);

  const [folderPath, setFolderPath] = useState<string>('');
  const [specimenName, setSpecimenName] = useState<string>('');
  const [preprocessResult, setPreprocessResult] = useState<PreprocessRunResponse | null>(null);
  const [initialData, setInitialData] = useState<InitialAutoDetectResponse | null>(null);
  const [batchConfigs, setBatchConfigs] = useState<GroupBatchConfig[]>([]);
  const [initialExcelPath, setInitialExcelPath] = useState<string>('');
  const [batchResults, setBatchResults] = useState<Record<string, BatchGroupResult>>({});

  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: 1,
      time: new Date().toLocaleTimeString('ja-JP', { hour12: false }),
      level: 'info',
      message: 'XRD AutoFit Studio ready',
    },
  ]);

  const appendLog = useCallback((message: string, level: 'info' | 'warn' | 'error' = 'info') => {
    setLogs((prev) => [
      ...prev.slice(-199),
      {
        id: Date.now() + Math.floor(Math.random() * 1000),
        time: new Date().toLocaleTimeString('ja-JP', { hour12: false }),
        level,
        message,
      },
    ]);
  }, []);

  // Global keyboard shortcuts: Ctrl+K (palette), Ctrl+B (sidebar), Ctrl+` (console)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setShowPalette((prev) => !prev);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setShowSidebar((prev) => !prev);
      } else if ((e.ctrlKey || e.metaKey) && (e.key === '`' || e.code === 'Backquote')) {
        e.preventDefault();
        setShowConsole((prev) => !prev);
      } else if (e.key === 'Escape') {
        setOpenMenu(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Close dropdown menu when clicking outside
  useEffect(() => {
    if (!openMenu) return;
    const close = () => setOpenMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [openMenu]);

  const totalOutlierCount = useMemo(
    () =>
      Object.values(batchResults).reduce(
        (acc, grp) => acc + (grp.outlier_nums?.length || 0),
        0
      ),
    [batchResults]
  );

  const hasBatchResults = Object.keys(batchResults).length > 0;

  const stepsMeta = useMemo(
    () => [
      {
        step: 1 as XrdStep,
        short: '前処理',
        title: '1. データ前処理・平滑化',
        done: Boolean(preprocessResult),
        badgeText: preprocessResult ? '済' : '待機',
        badgeTone: preprocessResult ? ('emerald' as const) : ('neutral' as const),
      },
      {
        step: 2 as XrdStep,
        short: '初期値決定',
        title: '2. 初期値・グループ決定',
        done: batchConfigs.length > 0 || Boolean(initialData),
        badgeText: batchConfigs.length > 0 ? `${batchConfigs.length}群` : initialData ? '検出済' : '待機',
        badgeTone: batchConfigs.length > 0 ? ('sky' as const) : ('neutral' as const),
      },
      {
        step: 3 as XrdStep,
        short: '一括Fit',
        title: '3. 全ファイル一括フィッティング',
        done: hasBatchResults,
        badgeText: hasBatchResults ? '完了' : '待機',
        badgeTone: hasBatchResults ? ('emerald' as const) : ('neutral' as const),
      },
      {
        step: 4 as XrdStep,
        short: '検証・出力',
        title: '4. 外れ値修正・Excel出力',
        done: false,
        badgeText: totalOutlierCount > 0 ? `外${totalOutlierCount}` : hasBatchResults ? '正常' : '待機',
        badgeTone:
          totalOutlierCount > 0
            ? ('amber' as const)
            : hasBatchResults
              ? ('emerald' as const)
              : ('neutral' as const),
      },
      {
        step: 5 as XrdStep,
        short: '物理量',
        title: '5. 相分率・転位密度解析',
        done: false,
        badgeText: hasBatchResults ? '実行可' : '任意',
        badgeTone: hasBatchResults ? ('sky' as const) : ('neutral' as const),
      },
    ],
    [preprocessResult, initialData, batchConfigs.length, hasBatchResults, totalOutlierCount]
  );

  const handleSelectFolderQuick = async () => {
    try {
      const res = await apiPost<{ path?: string }>('/api/dialog/select', {
        mode: 'folder',
        title: 'XRDデータフォルダを選択',
        initial_dir: folderPath || undefined,
      });
      if (res.path) {
        setFolderPath(res.path);
        appendLog(`フォルダ選択: ${res.path}`);
      }
    } catch (e: any) {
      appendLog(`フォルダ選択エラー: ${e.message}`, 'error');
    }
  };

  const handleCheckHealth = async () => {
    try {
      const res = await apiGet<{ status: string; version?: string }>('/api/health');
      appendLog(`Backend API: ${res.status}${res.version ? ` (v${res.version})` : ''}`);
      setShowConsole(true);
    } catch (e: any) {
      appendLog(`Health check failed: ${e.message}`, 'error');
      setShowConsole(true);
    }
  };

  const handleProceedStep2 = useCallback(() => {
    setMainMode('xrd');
    setXrdStep(2);
    appendLog(`Step 2 (初期値決定) へ移動${folderPath ? `: ${folderPath}` : ''}`);
  }, [folderPath, appendLog]);

  const handleConfirmInitialAndProceed = useCallback(
    (configs: GroupBatchConfig[], excelPath?: string) => {
      setBatchConfigs(configs);
      if (excelPath !== undefined) {
        setInitialExcelPath(excelPath);
      }
      setMainMode('xrd');
      setXrdStep(3);
      appendLog(`Step 3 (一括フィッティング) へ移動 (${configs.length} グループ)`);
    },
    [appendLog]
  );

  const handleProceedStep4 = useCallback(() => {
    setMainMode('xrd');
    setXrdStep(4);
    appendLog('Step 4 (波形検証・Excel出力) へ移動');
  }, [appendLog]);

  const handleProceedStep5 = useCallback(() => {
    setMainMode('xrd');
    setXrdStep(5);
    appendLog('Step 5 (物理量・転位密度解析) へ移動');
  }, [appendLog]);

  const commandItems: CommandItem[] = useMemo(
    () => [
      {
        id: 'step-1',
        label: 'Step 1: データ前処理・平滑化を開く',
        group: 'ナビゲーション',
        shortcut: '1',
        icon: <Folder className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(1);
        },
      },
      {
        id: 'step-2',
        label: 'Step 2: 初期値・グループ決定を開く',
        group: 'ナビゲーション',
        shortcut: '2',
        icon: <Layers className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(2);
        },
      },
      {
        id: 'step-3',
        label: 'Step 3: 一括フィッティングを開く',
        group: 'ナビゲーション',
        shortcut: '3',
        icon: <PlayCircle className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(3);
        },
      },
      {
        id: 'step-4',
        label: 'Step 4: 外れ値修正・Excel出力を開く',
        group: 'ナビゲーション',
        shortcut: '4',
        icon: <FileSpreadsheet className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(4);
        },
      },
      {
        id: 'step-5',
        label: 'Step 5: 相分率・転位密度解析を開く',
        group: 'ナビゲーション',
        shortcut: '5',
        icon: <BarChart3 className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(5);
        },
      },
      {
        id: 'mode-dic',
        label: 'DIC ひずみ・動画解析ユーティリティに切替',
        group: 'ワークスペース',
        icon: <Film className="w-3.5 h-3.5" />,
        onSelect: () => setMainMode('dic'),
      },
      {
        id: 'pick-folder',
        label: 'ファイル: データフォルダを選択...',
        group: 'アクション',
        icon: <Folder className="w-3.5 h-3.5" />,
        onSelect: handleSelectFolderQuick,
      },
      {
        id: 'toggle-sidebar',
        label: showSidebar ? '表示: エクスプローラーを閉じる' : '表示: エクスプローラーを開く',
        group: '表示',
        shortcut: 'Ctrl+B',
        icon: <PanelLeft className="w-3.5 h-3.5" />,
        onSelect: () => setShowSidebar((v) => !v),
      },
      {
        id: 'toggle-console',
        label: showConsole ? '表示: ログコンソールを閉じる' : '表示: ログコンソールを開く',
        group: '表示',
        shortcut: 'Ctrl+`',
        icon: <Terminal className="w-3.5 h-3.5" />,
        onSelect: () => setShowConsole((v) => !v),
      },
      {
        id: 'open-spec',
        label: 'ヘルプ: Voigtモデル・計算仕様を表示',
        group: 'ヘルプ',
        icon: <BookOpen className="w-3.5 h-3.5" />,
        onSelect: () => setShowSpecModal(true),
      },
      {
        id: 'check-health',
        label: '診断: Backend API 接続確認',
        group: 'システム',
        icon: <Activity className="w-3.5 h-3.5" />,
        onSelect: handleCheckHealth,
      },
    ],
    [showSidebar, showConsole, folderPath]
  );

  const activeStepMeta = stepsMeta.find((s) => s.step === xrdStep) || stepsMeta[0];

  return (
    <div className="h-dvh w-screen overflow-hidden flex flex-col bg-[#0d0e11] text-[#eceef2]">
      {/* Titlebar (38px) */}
      <header className="h-[38px] shrink-0 bg-[#121418] border-b border-[#23262e] px-2.5 flex items-center justify-between gap-2 select-none relative z-30">
        {/* Left: Brand & Menus */}
        <div className="flex items-center gap-1 min-w-0">
          <div className="flex items-center gap-2 pr-2 mr-1 border-r border-[#23262e]">
            <div className="w-5 h-5 rounded bg-[#1c1f26] border border-[#2e323d] flex items-center justify-center shrink-0">
              <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" aria-hidden="true">
                <path
                  d="M2 12 L5 12 L7.5 3.5 L10 12 L14 12"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M7.5 12 L10.5 6.5 L13.5 12"
                  fill="none"
                  stroke="#f59e0b"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <span className="text-[12px] font-semibold tracking-tight text-[#eceef2] whitespace-nowrap">
              XRD AutoFit Studio
            </span>
          </div>

          {/* Menu buttons */}
          <div className="hidden sm:flex items-center gap-0.5 text-[11px]">
            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                onClick={() => setOpenMenu((m) => (m === 'file' ? null : 'file'))}
                className={cn(
                  'h-6 px-2 rounded transition-colors',
                  openMenu === 'file'
                    ? 'bg-[#1c1f26] text-[#eceef2]'
                    : 'text-[#787f90] hover:text-[#eceef2] hover:bg-[#16181d]'
                )}
              >
                ファイル
              </button>
              {openMenu === 'file' && (
                <div className="absolute left-0 top-7 w-52 bg-[#16181d] border border-[#2e323d] rounded-md shadow-xl py-1 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setOpenMenu(null);
                      handleSelectFolderQuick();
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#b4b9c4] hover:bg-[#1c1f26] hover:text-[#eceef2] flex items-center justify-between"
                  >
                    <span>フォルダを選択...</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setOpenMenu(null);
                      setMainMode('xrd');
                      setXrdStep(1);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#b4b9c4] hover:bg-[#1c1f26] hover:text-[#eceef2]"
                  >
                    Step 1 (前処理) へ移動
                  </button>
                </div>
              )}
            </div>

            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                onClick={() => setOpenMenu((m) => (m === 'view' ? null : 'view'))}
                className={cn(
                  'h-6 px-2 rounded transition-colors',
                  openMenu === 'view'
                    ? 'bg-[#1c1f26] text-[#eceef2]'
                    : 'text-[#787f90] hover:text-[#eceef2] hover:bg-[#16181d]'
                )}
              >
                表示
              </button>
              {openMenu === 'view' && (
                <div className="absolute left-0 top-7 w-56 bg-[#16181d] border border-[#2e323d] rounded-md shadow-xl py-1 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setShowSidebar((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#b4b9c4] hover:bg-[#1c1f26] hover:text-[#eceef2] flex items-center justify-between"
                  >
                    <span>サイドバー表示切替</span>
                    <kbd className="text-[10px] font-mono text-[#787f90]">Ctrl+B</kbd>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowConsole((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#b4b9c4] hover:bg-[#1c1f26] hover:text-[#eceef2] flex items-center justify-between"
                  >
                    <span>ログコンソール切替</span>
                    <kbd className="text-[10px] font-mono text-[#787f90]">Ctrl+`</kbd>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowPalette(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#b4b9c4] hover:bg-[#1c1f26] hover:text-[#eceef2] flex items-center justify-between"
                  >
                    <span>コマンドパレット</span>
                    <kbd className="text-[10px] font-mono text-[#787f90]">Ctrl+K</kbd>
                  </button>
                </div>
              )}
            </div>

            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                onClick={() => setOpenMenu((m) => (m === 'help' ? null : 'help'))}
                className={cn(
                  'h-6 px-2 rounded transition-colors',
                  openMenu === 'help'
                    ? 'bg-[#1c1f26] text-[#eceef2]'
                    : 'text-[#787f90] hover:text-[#eceef2] hover:bg-[#16181d]'
                )}
              >
                ヘルプ
              </button>
              {openMenu === 'help' && (
                <div className="absolute left-0 top-7 w-52 bg-[#16181d] border border-[#2e323d] rounded-md shadow-xl py-1 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setShowSpecModal(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#b4b9c4] hover:bg-[#1c1f26] hover:text-[#eceef2]"
                  >
                    モデル仕様・ショートカット
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      handleCheckHealth();
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#b4b9c4] hover:bg-[#1c1f26] hover:text-[#eceef2]"
                  >
                    Backend API 疎通確認
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Center: Command trigger & Workspace Mode */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowPalette(true)}
            className="hidden md:flex items-center justify-between gap-4 w-60 h-[26px] px-2.5 bg-[#0a0b0e] border border-[#23262e] hover:border-[#2e323d] rounded text-[11px] text-[#787f90] transition-colors"
          >
            <span className="flex items-center gap-1.5 truncate">
              <Search className="w-3 h-3 shrink-0" />
              <span className="truncate">ステップ移動・操作を検索...</span>
            </span>
            <kbd className="text-[10px] font-mono bg-[#16181d] border border-[#23262e] px-1 rounded text-[#787f90] shrink-0">
              Ctrl+K
            </kbd>
          </button>

          <SegmentedControl<MainMode>
            ariaLabel="解析モード切替"
            size="sm"
            value={mainMode}
            onChange={setMainMode}
            options={[
              { value: 'xrd', label: 'XRD 解析', accent: 'sky' },
              { value: 'dic', label: 'DIC 動画', accent: 'emerald' },
            ]}
          />
        </div>

        {/* Right: Panel toggles & Spec */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setShowSidebar((v) => !v)}
            title="サイドバー切替 (Ctrl+B)"
            className={cn(
              'h-7 w-7 rounded flex items-center justify-center transition-colors',
              showSidebar
                ? 'bg-[#1c1f26] text-[#eceef2]'
                : 'text-[#787f90] hover:text-[#eceef2] hover:bg-[#16181d]'
            )}
          >
            <PanelLeft className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setShowConsole((v) => !v)}
            title="ログコンソール切替 (Ctrl+`)"
            className={cn(
              'h-7 w-7 rounded flex items-center justify-center transition-colors',
              showConsole
                ? 'bg-[#1c1f26] text-[#eceef2]'
                : 'text-[#787f90] hover:text-[#eceef2] hover:bg-[#16181d]'
            )}
          >
            <PanelBottom className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setShowSpecModal(true)}
            title="計算仕様・ショートカット"
            className="h-7 px-2 rounded flex items-center gap-1 text-[11px] text-[#787f90] hover:text-[#eceef2] hover:bg-[#16181d] transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">仕様</span>
          </button>
        </div>
      </header>

      {/* Main Workbench Area */}
      <div className="flex-1 min-h-0 flex">
        {/* Left Activity Rail (44px) */}
        <aside className="w-[44px] shrink-0 bg-[#121418] border-r border-[#23262e] flex flex-col items-center justify-between py-2 select-none">
          <div className="flex flex-col items-center gap-1.5 w-full">
            <button
              type="button"
              onClick={() => setMainMode('xrd')}
              title="XRD 解析ワークベンチ"
              className={cn(
                'relative w-full h-9 flex items-center justify-center transition-colors',
                mainMode === 'xrd'
                  ? 'text-[#38bdf8]'
                  : 'text-[#787f90] hover:text-[#b4b9c4]'
              )}
            >
              {mainMode === 'xrd' && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-[#38bdf8] rounded-r" />
              )}
              <Layers className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={() => setMainMode('dic')}
              title="DIC 動画・フレーム変換"
              className={cn(
                'relative w-full h-9 flex items-center justify-center transition-colors',
                mainMode === 'dic'
                  ? 'text-[#34d399]'
                  : 'text-[#787f90] hover:text-[#b4b9c4]'
              )}
            >
              {mainMode === 'dic' && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-[#34d399] rounded-r" />
              )}
              <Film className="w-4 h-4" />
            </button>
          </div>

          <div className="flex flex-col items-center gap-1.5 w-full">
            <button
              type="button"
              onClick={() => setShowPalette(true)}
              title="コマンドパレット (Ctrl+K)"
              className="w-full h-8 flex items-center justify-center text-[#787f90] hover:text-[#b4b9c4]"
            >
              <Command className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setShowSpecModal(true)}
              title="モデル仕様"
              className="w-full h-8 flex items-center justify-center text-[#787f90] hover:text-[#b4b9c4]"
            >
              <BookOpen className="w-4 h-4" />
            </button>
          </div>
        </aside>

        {/* Collapsible Explorer Sidebar (236px) */}
        {showSidebar && (
          <aside className="w-[236px] shrink-0 bg-[#121418] border-r border-[#23262e] flex flex-col min-h-0 select-none">
            <div className="px-3 py-2.5 border-b border-[#23262e]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-semibold text-[#b4b9c4]">
                  {mainMode === 'xrd' ? '解析パイプライン' : '動画ユーティリティ'}
                </span>
                <button
                  type="button"
                  onClick={handleSelectFolderQuick}
                  className="text-[10px] text-[#38bdf8] hover:underline whitespace-nowrap"
                >
                  フォルダ変更
                </button>
              </div>
              <div className="bg-[#0a0b0e] border border-[#23262e] rounded p-2 space-y-1">
                <div className="flex items-center justify-between text-[10px] text-[#787f90]">
                  <span>試験片</span>
                  <span className="font-mono text-[#b4b9c4] truncate max-w-[130px]">
                    {specimenName || '未設定'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10px] text-[#787f90]">
                  <span>フォルダ</span>
                  <span
                    className="font-mono text-[#b4b9c4] truncate max-w-[130px]"
                    title={folderPath || '未選択'}
                  >
                    {folderPath ? folderPath.split(/[\\/]/).filter(Boolean).pop() : '未選択'}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {mainMode === 'xrd' ? (
                stepsMeta.map((item) => {
                  const isActive = item.step === xrdStep;
                  return (
                    <button
                      key={item.step}
                      type="button"
                      onClick={() => setXrdStep(item.step)}
                      className={cn(
                        'w-full px-2.5 py-2 rounded text-left flex items-center justify-between gap-2 transition-colors border',
                        isActive
                          ? 'bg-[#1c1f26] border-[#2e323d] text-[#eceef2]'
                          : 'bg-transparent border-transparent text-[#787f90] hover:bg-[#16181d] hover:text-[#b4b9c4]'
                      )}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            'font-mono text-[10px] tabular-nums w-4 text-center shrink-0',
                            isActive ? 'text-[#38bdf8]' : 'text-[#525866]'
                          )}
                        >
                          0{item.step}
                        </span>
                        <span className="text-[12px] font-medium truncate">{item.short}</span>
                      </div>
                      <StatusBadge tone={item.badgeTone} mono>
                        {item.badgeText}
                      </StatusBadge>
                    </button>
                  );
                })
              ) : (
                <div className="px-2.5 py-2 rounded bg-[#1c1f26] border border-[#2e323d] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Film className="w-3.5 h-3.5 text-[#34d399]" />
                    <span className="text-[12px] font-medium text-[#eceef2]">動画切り出し・DIC</span>
                  </div>
                  <StatusBadge tone="emerald">有効</StatusBadge>
                </div>
              )}
            </div>

            <div className="px-3 py-2 border-t border-[#23262e] text-[10px] text-[#787f90] space-y-1">
              <div className="flex items-center justify-between">
                <span>クイック移動</span>
                <kbd className="font-mono bg-[#16181d] border border-[#23262e] px-1 rounded">
                  Ctrl+K
                </kbd>
              </div>
              <div className="flex items-center justify-between">
                <span>サイドバー</span>
                <kbd className="font-mono bg-[#16181d] border border-[#23262e] px-1 rounded">
                  Ctrl+B
                </kbd>
              </div>
            </div>
          </aside>
        )}

        {/* Center Workbench Stage */}
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          {/* Document Tab Strip (36px) */}
          <div className="h-[36px] shrink-0 bg-[#121418] border-b border-[#23262e] flex items-center justify-between px-2 overflow-x-auto select-none">
            <div className="flex items-center h-full">
              {mainMode === 'xrd' ? (
                stepsMeta.map((item) => {
                  const isActive = item.step === xrdStep;
                  return (
                    <button
                      key={item.step}
                      type="button"
                      onClick={() => setXrdStep(item.step)}
                      className={cn(
                        'relative h-full px-3 text-[11px] font-medium flex items-center gap-1.5 border-r border-[#23262e] whitespace-nowrap transition-colors',
                        isActive
                          ? 'bg-[#0d0e11] text-[#eceef2]'
                          : 'bg-transparent text-[#787f90] hover:text-[#b4b9c4] hover:bg-[#16181d]'
                      )}
                    >
                      {isActive && (
                        <span className="absolute top-0 left-0 right-0 h-[2px] bg-[#38bdf8]" />
                      )}
                      {item.done && (
                        <CheckCircle2 className="w-3 h-3 text-[#34d399] shrink-0" />
                      )}
                      <span>{item.step}. {item.short}</span>
                      {item.step === 4 && totalOutlierCount > 0 && (
                        <span className="ml-0.5 px-1.5 py-0 rounded-full bg-[#f59e0b]/15 text-[#f59e0b] text-[10px] font-mono tabular-nums">
                          {totalOutlierCount}
                        </span>
                      )}
                    </button>
                  );
                })
              ) : (
                <div className="relative h-full px-3.5 text-[11px] font-medium flex items-center gap-1.5 border-r border-[#23262e] bg-[#0d0e11] text-[#eceef2] whitespace-nowrap">
                  <span className="absolute top-0 left-0 right-0 h-[2px] bg-[#34d399]" />
                  <Film className="w-3.5 h-3.5 text-[#34d399]" />
                  <span>動画検査・AVI / TIFF 変換ユーティリティ</span>
                </div>
              )}
            </div>

            {mainMode === 'xrd' && (
              <div className="hidden lg:flex items-center gap-1 text-[11px] text-[#787f90] pr-2 whitespace-nowrap">
                <span>XRD</span>
                <ChevronRight className="w-3 h-3" />
                <span className="text-[#b4b9c4]">{activeStepMeta.title}</span>
              </div>
            )}
          </div>

          {/* Scrollable Main View */}
          <main className="flex-1 min-h-0 overflow-y-auto p-4 bg-[#0d0e11]">
            <div className="max-w-[1600px] mx-auto">
              {mainMode === 'dic' ? (
                <VideoUtilityTab />
              ) : xrdStep === 1 ? (
                <Step1Preprocess
                  folderPath={folderPath}
                  setFolderPath={setFolderPath}
                  specimenName={specimenName}
                  setSpecimenName={setSpecimenName}
                  preprocessResult={preprocessResult}
                  setPreprocessResult={setPreprocessResult}
                  onProceedStep2={handleProceedStep2}
                />
              ) : xrdStep === 2 ? (
                <Step2InitialPick
                  folderPath={folderPath}
                  specimenName={specimenName}
                  initialData={initialData}
                  setInitialData={setInitialData}
                  onConfirmInitialAndProceed={handleConfirmInitialAndProceed}
                />
              ) : xrdStep === 3 ? (
                <Step3BatchRun
                  folderPath={folderPath}
                  specimenName={specimenName}
                  initialExcelPath={initialExcelPath}
                  batchConfigs={batchConfigs}
                  setBatchConfigs={setBatchConfigs}
                  batchResults={batchResults}
                  setBatchResults={setBatchResults}
                  onProceedStep4={handleProceedStep4}
                />
              ) : xrdStep === 4 ? (
                <Step4ReviewExport
                  folderPath={folderPath}
                  specimenName={specimenName}
                  batchResults={batchResults}
                  setBatchResults={setBatchResults}
                  onProceedStep5={handleProceedStep5}
                />
              ) : (
                <Step5PhysicsAnalysis
                  folderPath={folderPath}
                  specimenName={specimenName}
                  batchResults={batchResults}
                />
              )}
            </div>
          </main>

          {/* Collapsible Bottom Console (168px) */}
          {showConsole && (
            <section className="h-[168px] shrink-0 bg-[#0a0b0e] border-t border-[#23262e] flex flex-col min-h-0">
              <div className="h-7 px-3 border-b border-[#23262e] bg-[#121418] flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-2 text-[#b4b9c4] font-medium">
                  <Terminal className="w-3.5 h-3.5 text-[#38bdf8]" />
                  <span>出力ログ</span>
                  <span className="font-mono text-[10px] text-[#787f90] tabular-nums">
                    ({logs.length})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setLogs([])}
                    className="text-[10px] text-[#787f90] hover:text-[#eceef2]"
                  >
                    クリア
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowConsole(false)}
                    className="text-[10px] text-[#787f90] hover:text-[#eceef2]"
                  >
                    閉じる
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-3 py-1.5 font-mono text-[11px] space-y-0.5 tabular-nums">
                {logs.length === 0 ? (
                  <div className="text-[#525866]">ログはありません</div>
                ) : (
                  logs.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-2.5">
                      <span className="text-[#525866] shrink-0">{entry.time}</span>
                      <span
                        className={cn(
                          'shrink-0 uppercase text-[10px]',
                          entry.level === 'error'
                            ? 'text-[#fb7185]'
                            : entry.level === 'warn'
                              ? 'text-[#f59e0b]'
                              : 'text-[#38bdf8]'
                        )}
                      >
                        {entry.level}
                      </span>
                      <span className="text-[#b4b9c4] break-all">{entry.message}</span>
                    </div>
                  ))
                )}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* Footer Status Bar (24px) */}
      <footer className="h-[24px] shrink-0 bg-[#121418] border-t border-[#23262e] px-3 flex items-center justify-between text-[11px] font-mono tabular-nums text-[#787f90] select-none">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[#b4b9c4] whitespace-nowrap">
            {mainMode === 'xrd' ? `XRD Step ${xrdStep}/5` : 'DIC Utility'}
          </span>
          {specimenName && (
            <span className="truncate max-w-[160px]" title={specimenName}>
              Specimen: {specimenName}
            </span>
          )}
          {folderPath && (
            <span className="hidden md:inline truncate max-w-[300px]" title={folderPath}>
              Dir: {folderPath}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {hasBatchResults && (
            <button
              type="button"
              onClick={() => {
                setMainMode('xrd');
                setXrdStep(4);
              }}
              className={cn(
                'hover:underline whitespace-nowrap',
                totalOutlierCount > 0 ? 'text-[#f59e0b]' : 'text-[#34d399]'
              )}
            >
              Outliers: {totalOutlierCount}
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowConsole((v) => !v)}
            className="hover:text-[#eceef2] whitespace-nowrap"
          >
            Log ({logs.length})
          </button>
          <span className="whitespace-nowrap">
            {isDesktopBridge() ? 'Desktop IPC' : 'Local API'}
          </span>
        </div>
      </footer>

      {/* Modals */}
      <CommandPalette
        open={showPalette}
        onClose={() => setShowPalette(false)}
        items={commandItems}
      />
      <ModelSpecModal open={showSpecModal} onClose={() => setShowSpecModal(false)} />
    </div>
  );
};

export default App;
