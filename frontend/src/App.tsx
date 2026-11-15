import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  BookOpen,
  Check,
  Command,
  Compass,
  FileSpreadsheet,
  Film,
  Folder,
  FolderOpen,
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
import { WORKFLOW_GUIDE_STEPS, WorkflowGuide } from './components/WorkflowGuide';

type MainMode = 'xrd' | 'dic';
type XrdStep = 1 | 2 | 3 | 4 | 5;

const GUIDE_DISMISSED_KEY = 'xrd_autofit_guide_dismissed_v1';

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

  const [guideActive, setGuideActive] = useState<boolean>(() => {
    try {
      return localStorage.getItem(GUIDE_DISMISSED_KEY) !== '1';
    } catch {
      return true;
    }
  });
  const [guideStepIndex, setGuideStepIndex] = useState<number>(0);
  const [folderPickSeq, setFolderPickSeq] = useState<number>(0);
  const [step2SubScreen, setStep2SubScreen] = useState<'overview' | 'detail'>('overview');
  const [physicsComputed, setPhysicsComputed] = useState<boolean>(false);

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
        label: '前処理',
        subtitle: 'スパイク・ベースライン除去',
        done: Boolean(preprocessResult),
        indicator: preprocessResult ? ('done' as const) : null,
      },
      {
        step: 2 as XrdStep,
        label: '初期値',
        subtitle: 'ピーク検出・詳細Fit検証',
        done: batchConfigs.length > 0 || Boolean(initialData),
        indicator:
          batchConfigs.length > 0
            ? (`${batchConfigs.length}` as const)
            : initialData
              ? ('done' as const)
              : null,
      },
      {
        step: 3 as XrdStep,
        label: '一括Fit',
        subtitle: '全フレーム連続最適化',
        done: hasBatchResults,
        indicator: hasBatchResults ? ('done' as const) : null,
      },
      {
        step: 4 as XrdStep,
        label: '検証・出力',
        subtitle: '外れ値修正・Excel出力',
        done: false,
        indicator:
          totalOutlierCount > 0
            ? (`外${totalOutlierCount}` as const)
            : hasBatchResults
              ? ('done' as const)
              : null,
      },
      {
        step: 5 as XrdStep,
        label: '物理量',
        subtitle: '相分率・転位密度算出',
        done: physicsComputed,
        indicator: physicsComputed ? ('done' as const) : null,
      },
    ],
    [
      preprocessResult,
      initialData,
      batchConfigs.length,
      hasBatchResults,
      totalOutlierCount,
      physicsComputed,
    ]
  );

  const completedStepsCount = useMemo(
    () => stepsMeta.filter((s) => s.done).length,
    [stepsMeta]
  );

  const handleToggleGuide = useCallback(() => {
    setGuideActive((prev) => {
      const next = !prev;
      try {
        if (next) {
          localStorage.removeItem(GUIDE_DISMISSED_KEY);
        } else {
          localStorage.setItem(GUIDE_DISMISSED_KEY, '1');
        }
      } catch {
        // ignore storage restrictions
      }
      return next;
    });
  }, []);

  const handleCloseGuide = useCallback(() => {
    setGuideActive(false);
    try {
      localStorage.setItem(GUIDE_DISMISSED_KEY, '1');
    } catch {
      // ignore
    }
  }, []);

  const handleNavigateFromGuide = useCallback((mode?: MainMode, step?: XrdStep) => {
    if (mode) setMainMode(mode);
    if (step) setXrdStep(step);
  }, []);

  const handleSelectFolderQuick = async () => {
    try {
      const res = await apiPost<{ selected_path?: string; path?: string; cancelled?: boolean }>(
        '/api/dialog/select',
        {
          mode: 'folder',
          title: 'フォルダ選択',
          initial_dir: folderPath || undefined,
        }
      );
      const picked = res.selected_path || res.path;
      if (!res.cancelled && picked) {
        setFolderPath(picked);
        setFolderPickSeq((s) => s + 1);
        appendLog(`フォルダ選択: ${picked}`);
      }
    } catch (e: any) {
      appendLog(`フォルダ選択エラー: ${e.message}`, 'error');
    }
  };

  const handleCheckHealth = async () => {
    try {
      const res = await apiGet<{ status: string; version?: string }>('/api/health');
      appendLog(`API: ${res.status}${res.version ? ` v${res.version}` : ''}`);
      setShowConsole(true);
    } catch (e: any) {
      appendLog(`Health check failed: ${e.message}`, 'error');
      setShowConsole(true);
    }
  };

  const handleProceedStep2 = useCallback(() => {
    setMainMode('xrd');
    setXrdStep(2);
    appendLog(`Step 2${folderPath ? `: ${folderPath}` : ''}`);
  }, [folderPath, appendLog]);

  const handleConfirmInitialAndProceed = useCallback(
    (configs: GroupBatchConfig[], excelPath?: string) => {
      setBatchConfigs(configs);
      if (excelPath !== undefined) {
        setInitialExcelPath(excelPath);
      }
      setMainMode('xrd');
      setXrdStep(3);
      appendLog(`Step 3 (${configs.length} groups)`);
    },
    [appendLog]
  );

  const handleProceedStep4 = useCallback(() => {
    setMainMode('xrd');
    setXrdStep(4);
    appendLog('Step 4');
  }, [appendLog]);

  const handleProceedStep5 = useCallback(() => {
    setMainMode('xrd');
    setXrdStep(5);
    appendLog('Step 5');
  }, [appendLog]);

  const commandItems: CommandItem[] = useMemo(
    () => [
      {
        id: 'step-1',
        label: '1 前処理',
        group: '移動',
        shortcut: '1',
        icon: <Folder className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(1);
        },
      },
      {
        id: 'step-2',
        label: '2 初期値',
        group: '移動',
        shortcut: '2',
        icon: <Layers className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(2);
        },
      },
      {
        id: 'step-3',
        label: '3 一括Fit',
        group: '移動',
        shortcut: '3',
        icon: <PlayCircle className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(3);
        },
      },
      {
        id: 'step-4',
        label: '4 検証・出力',
        group: '移動',
        shortcut: '4',
        icon: <FileSpreadsheet className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(4);
        },
      },
      {
        id: 'step-5',
        label: '5 物理量',
        group: '移動',
        shortcut: '5',
        icon: <BarChart3 className="w-3.5 h-3.5" />,
        onSelect: () => {
          setMainMode('xrd');
          setXrdStep(5);
        },
      },
      {
        id: 'mode-dic',
        label: 'DIC フレーム抽出',
        group: 'モード',
        icon: <Film className="w-3.5 h-3.5" />,
        onSelect: () => setMainMode('dic'),
      },
      {
        id: 'pick-folder',
        label: 'フォルダを選択...',
        group: 'ファイル',
        icon: <FolderOpen className="w-3.5 h-3.5" />,
        onSelect: handleSelectFolderQuick,
      },
      {
        id: 'toggle-sidebar',
        label: 'サイドバー切替',
        group: '表示',
        shortcut: 'Ctrl+B',
        icon: <PanelLeft className="w-3.5 h-3.5" />,
        onSelect: () => setShowSidebar((v) => !v),
      },
      {
        id: 'toggle-console',
        label: 'コンソール切替',
        group: '表示',
        shortcut: 'Ctrl+`',
        icon: <Terminal className="w-3.5 h-3.5" />,
        onSelect: () => setShowConsole((v) => !v),
      },
      {
        id: 'open-guide',
        label: '操作ナビゲーションガイドを開始',
        group: 'ヘルプ',
        icon: <Compass className="w-4 h-4 text-sky-400" />,
        onSelect: () => {
          setGuideStepIndex(0);
          setGuideActive(true);
          try {
            localStorage.removeItem(GUIDE_DISMISSED_KEY);
          } catch {
            // ignore
          }
        },
      },
      {
        id: 'open-spec',
        label: 'モデル仕様・ショートカット',
        group: 'ヘルプ',
        icon: <BookOpen className="w-3.5 h-3.5" />,
        onSelect: () => setShowSpecModal(true),
      },
      {
        id: 'check-health',
        label: 'API 疎通確認',
        group: '診断',
        icon: <Activity className="w-3.5 h-3.5" />,
        onSelect: handleCheckHealth,
      },
    ],
    [folderPath]
  );

  const folderShortName = folderPath
    ? folderPath.split(/[\\/]/).filter(Boolean).pop() || folderPath
    : '未選択';

  return (
    <div className="h-dvh w-screen overflow-hidden flex flex-col bg-[#0b0c0f] text-[#eef0f4]">
      {/* Titlebar (46px) */}
      <header className="h-[46px] shrink-0 bg-[#101216] border-b border-[#252a35] px-3 flex items-center justify-between gap-2 select-none relative z-30">
        <div className="flex items-center gap-1.5 min-w-0">
          <div className="flex items-center gap-2.5 pr-3 mr-1 border-r border-[#252a35]">
            <div className="w-7 h-7 rounded-md bg-gradient-to-b from-[#1e2430] to-[#141820] border border-[#323949] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] flex items-center justify-center shrink-0">
              <svg viewBox="0 0 16 16" className="w-4 h-4" aria-hidden="true">
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
            <span className="text-[13px] font-bold tracking-tight text-[#eef0f4] whitespace-nowrap">
              XRD AutoFit Studio
            </span>
          </div>

          <div className="hidden md:flex items-center gap-0.5 text-[12px]">
            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                onClick={() => setOpenMenu((m) => (m === 'file' ? null : 'file'))}
                className={cn(
                  'h-7 px-2.5 rounded-md transition-colors',
                  openMenu === 'file'
                    ? 'bg-[#1c2028] text-[#eef0f4]'
                    : 'text-[#98a0ae] hover:text-[#eef0f4] hover:bg-[#171b23]'
                )}
              >
                ファイル
              </button>
              {openMenu === 'file' && (
                <div className="absolute left-0 top-8 w-52 bg-[#15181e] border border-[#303644] rounded-lg shadow-2xl py-1.5 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setOpenMenu(null);
                      handleSelectFolderQuick();
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    解析フォルダ選択...
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setOpenMenu(null);
                      setMainMode('xrd');
                      setXrdStep(1);
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    Step 1 前処理へ
                  </button>
                </div>
              )}
            </div>

            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                onClick={() => setOpenMenu((m) => (m === 'view' ? null : 'view'))}
                className={cn(
                  'h-7 px-2.5 rounded-md transition-colors',
                  openMenu === 'view'
                    ? 'bg-[#1c2028] text-[#eef0f4]'
                    : 'text-[#98a0ae] hover:text-[#eef0f4] hover:bg-[#171b23]'
                )}
              >
                表示
              </button>
              {openMenu === 'view' && (
                <div className="absolute left-0 top-8 w-56 bg-[#15181e] border border-[#303644] rounded-lg shadow-2xl py-1.5 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setShowSidebar((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-[#cfd4de] hover:bg-[#1f242e] flex items-center justify-between"
                  >
                    <span>サイドバー</span>
                    <kbd className="text-[11px] font-mono text-[#7c8494]">Ctrl+B</kbd>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowConsole((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-[#cfd4de] hover:bg-[#1f242e] flex items-center justify-between"
                  >
                    <span>コンソール</span>
                    <kbd className="text-[11px] font-mono text-[#7c8494]">Ctrl+`</kbd>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowPalette(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-[#cfd4de] hover:bg-[#1f242e] flex items-center justify-between"
                  >
                    <span>コマンドパレット</span>
                    <kbd className="text-[11px] font-mono text-[#7c8494]">Ctrl+K</kbd>
                  </button>
                </div>
              )}
            </div>

            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                onClick={() => setOpenMenu((m) => (m === 'help' ? null : 'help'))}
                className={cn(
                  'h-7 px-2.5 rounded-md transition-colors',
                  openMenu === 'help'
                    ? 'bg-[#1c2028] text-[#eef0f4]'
                    : 'text-[#98a0ae] hover:text-[#eef0f4] hover:bg-[#171b23]'
                )}
              >
                ヘルプ
              </button>
              {openMenu === 'help' && (
                <div className="absolute left-0 top-8 w-56 bg-[#15181e] border border-[#303644] rounded-lg shadow-2xl py-1.5 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setGuideStepIndex(0);
                      setGuideActive(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-sky-300 font-medium hover:bg-[#1f242e]"
                  >
                    操作ナビゲーションガイド
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowSpecModal(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    モデル仕様・ショートカット
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      handleCheckHealth();
                      setOpenMenu(null);
                    }}
                    className="w-full px-3.5 py-2 text-left text-[12px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    API 接続確認
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Workspace Controls: Search + Emphasized XRD/DIC Mode Switcher + Guide + Utilities */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setShowPalette(true)}
            className="hidden xl:flex items-center justify-between gap-3 w-44 h-8 px-2.5 bg-[#08090c] border border-[#252a35] hover:border-[#373f52] rounded-md text-[12px] text-[#7c8494] transition-colors"
          >
            <span className="flex items-center gap-1.5 truncate">
              <Search className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">検索 / コマンド</span>
            </span>
            <kbd className="text-[10px] font-mono bg-[#15181e] border border-[#252a35] px-1.5 py-0.5 rounded text-[#98a0ae] shrink-0">
              Ctrl+K
            </kbd>
          </button>

          {/* Emphasized Dual-Mode Switcher (XRD vs DIC) */}
          <div
            role="tablist"
            aria-label="解析モード"
            data-guide="mode-switcher"
            className="inline-flex items-center p-1 rounded-lg bg-[#08090c] border border-[#2c3342] gap-1 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)]"
          >
            <button
              role="tab"
              type="button"
              aria-selected={mainMode === 'xrd'}
              onClick={() => setMainMode('xrd')}
              className={cn(
                'h-8 px-3 rounded-md border flex items-center gap-2 transition-all whitespace-nowrap',
                mainMode === 'xrd'
                  ? 'bg-gradient-to-b from-sky-500/25 to-sky-500/10 border-sky-400/75 text-sky-100 shadow-[0_0_16px_-4px_rgba(56,189,248,0.55)] font-semibold'
                  : 'border-transparent text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#151922] font-medium'
              )}
            >
              <span
                className={cn(
                  'w-2 h-2 rounded-full shrink-0',
                  mainMode === 'xrd'
                    ? 'bg-sky-400 shadow-[0_0_8px_rgba(56,189,248,0.9)]'
                    : 'bg-[#3d4454]'
                )}
              />
              <Layers className="w-3.5 h-3.5 text-sky-400 shrink-0" />
              <span className="text-[12px] tracking-tight">XRD 回折・相解析</span>
            </button>

            <button
              role="tab"
              type="button"
              aria-selected={mainMode === 'dic'}
              onClick={() => setMainMode('dic')}
              className={cn(
                'h-8 px-3 rounded-md border flex items-center gap-2 transition-all whitespace-nowrap',
                mainMode === 'dic'
                  ? 'bg-gradient-to-b from-amber-500/25 to-amber-500/10 border-amber-400/75 text-amber-100 shadow-[0_0_16px_-4px_rgba(245,158,11,0.55)] font-semibold'
                  : 'border-transparent text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#151922] font-medium'
              )}
            >
              <span
                className={cn(
                  'w-2 h-2 rounded-full shrink-0',
                  mainMode === 'dic'
                    ? 'bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.9)]'
                    : 'bg-[#3d4454]'
                )}
              />
              <Film className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="text-[12px] tracking-tight">DIC 動画フレーム抽出</span>
            </button>
          </div>

          {/* Guide Launch Button */}
          <button
            type="button"
            onClick={handleToggleGuide}
            title="ステップごとのアニメーションガイド表示/非表示"
            className={cn(
              'h-8 px-2.5 rounded-md border flex items-center gap-1.5 text-[12px] font-medium transition-all whitespace-nowrap',
              guideActive
                ? 'bg-sky-500/18 border-sky-400/60 text-sky-200 shadow-[0_0_12px_-4px_rgba(56,189,248,0.5)]'
                : 'bg-[#171b23] border-[#2c3240] text-[#cfd4de] hover:border-sky-500/50 hover:text-sky-200'
            )}
          >
            <Compass className={cn('w-3.5 h-3.5', guideActive && 'text-sky-300')} />
            <span>
              {guideActive
                ? `ガイド ${guideStepIndex + 1}/${WORKFLOW_GUIDE_STEPS.length}`
                : '操作ガイド'}
            </span>
          </button>

          <div className="flex items-center gap-1 pl-1 border-l border-[#252a35]">
            <button
              type="button"
              onClick={() => setShowSidebar((v) => !v)}
              title="サイドバー (Ctrl+B)"
              className={cn(
                'h-8 w-8 rounded-md flex items-center justify-center transition-colors',
                showSidebar
                  ? 'bg-[#1c2028] text-[#eef0f4]'
                  : 'text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#171b23]'
              )}
            >
              <PanelLeft className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setShowConsole((v) => !v)}
              title="コンソール (Ctrl+`)"
              className={cn(
                'h-8 w-8 rounded-md flex items-center justify-center transition-colors',
                showConsole
                  ? 'bg-[#1c2028] text-[#eef0f4]'
                  : 'text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#171b23]'
              )}
            >
              <PanelBottom className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setShowSpecModal(true)}
              title="モデル仕様"
              className="h-8 px-2 rounded-md flex items-center gap-1 text-[12px] text-[#98a0ae] hover:text-[#eef0f4] hover:bg-[#171b23] transition-colors whitespace-nowrap"
            >
              <HelpCircle className="w-4 h-4" />
              <span className="hidden lg:inline">仕様</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Workbench */}
      <div className="flex-1 min-h-0 flex">
        {/* Activity Rail (54px) */}
        <aside className="w-[54px] shrink-0 bg-[#101216] border-r border-[#252a35] flex flex-col items-center justify-between py-2.5 select-none">
          <div className="flex flex-col items-center gap-1.5 w-full px-1">
            <button
              type="button"
              onClick={() => setMainMode('xrd')}
              title="XRD 回折・相解析モード"
              className={cn(
                'relative w-full py-2 rounded-lg flex flex-col items-center justify-center gap-1 transition-all',
                mainMode === 'xrd'
                  ? 'bg-sky-500/15 text-sky-300 border border-sky-500/35'
                  : 'text-[#6c7587] hover:text-[#cfd4de] hover:bg-[#171b23]'
              )}
            >
              {mainMode === 'xrd' && (
                <span className="absolute left-0 top-2 bottom-2 w-[3px] bg-sky-400 rounded-r" />
              )}
              <Layers className="w-4 h-4" />
              <span className="text-[9px] font-bold tracking-wider">XRD</span>
            </button>

            <button
              type="button"
              onClick={() => setMainMode('dic')}
              title="DIC 動画フレーム抽出モード"
              className={cn(
                'relative w-full py-2 rounded-lg flex flex-col items-center justify-center gap-1 transition-all',
                mainMode === 'dic'
                  ? 'bg-amber-500/15 text-amber-300 border border-amber-500/35'
                  : 'text-[#6c7587] hover:text-[#cfd4de] hover:bg-[#171b23]'
              )}
            >
              {mainMode === 'dic' && (
                <span className="absolute left-0 top-2 bottom-2 w-[3px] bg-amber-400 rounded-r" />
              )}
              <Film className="w-4 h-4" />
              <span className="text-[9px] font-bold tracking-wider">DIC</span>
            </button>
          </div>

          <div className="flex flex-col items-center gap-1.5 w-full px-1">
            <button
              type="button"
              onClick={handleToggleGuide}
              title="操作ナビゲーションガイド"
              className={cn(
                'w-full py-2 rounded-lg flex flex-col items-center justify-center gap-0.5 transition-colors',
                guideActive
                  ? 'text-sky-300 bg-sky-500/15 border border-sky-500/35'
                  : 'text-[#6c7587] hover:text-[#cfd4de] hover:bg-[#171b23]'
              )}
            >
              <Compass className="w-4 h-4" />
              <span className="text-[9px] font-medium">案内</span>
            </button>
            <button
              type="button"
              onClick={() => setShowPalette(true)}
              title="Ctrl+K"
              className="w-full h-9 rounded-lg flex items-center justify-center text-[#6c7587] hover:text-[#cfd4de] hover:bg-[#171b23]"
            >
              <Command className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setShowSpecModal(true)}
              title="モデル仕様"
              className="w-full h-9 rounded-lg flex items-center justify-center text-[#6c7587] hover:text-[#cfd4de] hover:bg-[#171b23]"
            >
              <BookOpen className="w-4 h-4" />
            </button>
          </div>
        </aside>

        {/* Explorer Sidebar (248px) */}
        {showSidebar && (
          <aside className="w-[248px] shrink-0 bg-[#101216] border-r border-[#252a35] flex flex-col min-h-0 select-none">
            <div className="p-3 border-b border-[#252a35] space-y-2.5">
              <button
                type="button"
                onClick={handleSelectFolderQuick}
                title={folderPath || 'フォルダ選択'}
                className="w-full px-3 py-2.5 rounded-lg bg-[#08090c] border border-[#272c37] hover:border-sky-500/45 flex items-center justify-between gap-2 transition-colors text-left"
              >
                <div className="min-w-0">
                  <div className="text-[12px] font-semibold text-[#eef0f4] truncate">
                    {specimenName || folderShortName}
                  </div>
                  <div className="text-[11px] font-mono text-[#7c8494] truncate mt-0.5">
                    {folderShortName}
                  </div>
                </div>
                <FolderOpen className="w-4 h-4 text-sky-400 shrink-0" />
              </button>

              {mainMode === 'xrd' && (
                <div className="px-1">
                  <div className="flex items-center justify-between text-[11px] text-[#858d9c] mb-1.5">
                    <span className="font-medium">XRD ワークフロー</span>
                    <span className="font-mono tabular-nums text-[#cfd4de]">
                      {completedStepsCount} / 5
                    </span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-[#08090c] border border-[#222630] overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-sky-400 to-emerald-400 transition-all duration-300"
                      style={{ width: `${(completedStepsCount / 5) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {mainMode === 'xrd' ? (
                stepsMeta.map((item) => {
                  const isActive = item.step === xrdStep;
                  return (
                    <button
                      key={item.step}
                      type="button"
                      data-guide={`nav-step-${item.step}`}
                      onClick={() => setXrdStep(item.step)}
                      className={cn(
                        'relative w-full px-3 py-2.5 rounded-lg text-left flex items-center justify-between gap-2 transition-all border',
                        isActive
                          ? 'bg-gradient-to-r from-[#1a2230] to-[#151820] border-sky-500/40 text-[#eef0f4] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]'
                          : 'bg-transparent border-transparent text-[#98a0ae] hover:bg-[#151820] hover:text-[#eef0f4]'
                      )}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-2 bottom-2 w-[3px] bg-sky-400 rounded-r" />
                      )}
                      <div className="flex items-start gap-2.5 min-w-0">
                        <span
                          className={cn(
                            'mt-0.5 w-5 h-5 rounded font-mono text-[11px] font-semibold tabular-nums flex items-center justify-center shrink-0 border',
                            isActive
                              ? 'bg-sky-500/20 border-sky-400/50 text-sky-300'
                              : item.done
                                ? 'bg-emerald-500/15 border-emerald-500/35 text-emerald-300'
                                : 'bg-[#15181e] border-[#252a35] text-[#7c8494]'
                          )}
                        >
                          {item.step}
                        </span>
                        <div className="min-w-0">
                          <div className="text-[13px] font-semibold truncate">{item.label}</div>
                          <div className="text-[11px] text-[#7c8494] truncate mt-0.5">
                            {item.subtitle}
                          </div>
                        </div>
                      </div>

                      {item.indicator === 'done' ? (
                        <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                      ) : item.indicator ? (
                        <span
                          className={cn(
                            'text-[11px] font-mono tabular-nums px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap',
                            item.step === 4 && totalOutlierCount > 0
                              ? 'bg-amber-500/15 text-amber-300 border border-amber-500/35'
                              : 'bg-[#1d212a] text-[#cfd4de]'
                          )}
                        >
                          {item.indicator}
                        </span>
                      ) : null}
                    </button>
                  );
                })
              ) : (
                <div className="relative px-3 py-3 rounded-lg bg-gradient-to-r from-amber-500/15 to-[#151820] border border-amber-500/40 text-[#eef0f4] flex items-center gap-2.5">
                  <span className="absolute left-0 top-2 bottom-2 w-[3px] bg-amber-400 rounded-r" />
                  <Film className="w-4 h-4 text-amber-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold truncate">フレーム抽出</div>
                    <div className="text-[11px] text-[#98a0ae] truncate mt-0.5">
                      DIC用連番静止画切出
                    </div>
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}

        {/* Center Workbench Stage */}
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          {/* Flat Document Tab Strip (40px) */}
          <div className="h-[40px] shrink-0 bg-[#101216] border-b border-[#252a35] flex items-center overflow-x-auto select-none">
            {mainMode === 'xrd' ? (
              stepsMeta.map((item) => {
                const isActive = item.step === xrdStep;
                return (
                  <button
                    key={item.step}
                    type="button"
                    onClick={() => setXrdStep(item.step)}
                    className={cn(
                      'relative h-full px-4 text-[13px] font-medium flex items-center gap-2 border-r border-[#252a35] whitespace-nowrap transition-colors',
                      isActive
                        ? 'bg-[#0b0c0f] text-[#eef0f4] font-semibold'
                        : 'bg-transparent text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#161a22]'
                    )}
                  >
                    {isActive && (
                      <span className="absolute top-0 left-0 right-0 h-[2px] bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.8)]" />
                    )}
                    <span className={cn('font-mono text-[11px]', isActive ? 'text-sky-400' : 'text-[#636b78]')}>
                      {item.step}.
                    </span>
                    <span>{item.label}</span>
                    {item.done && <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />}
                    {item.step === 4 && totalOutlierCount > 0 && (
                      <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 text-[11px] font-mono tabular-nums">
                        {totalOutlierCount}
                      </span>
                    )}
                  </button>
                );
              })
            ) : (
              <div className="relative h-full px-4 text-[13px] font-semibold flex items-center gap-2 border-r border-[#252a35] bg-[#0b0c0f] text-[#eef0f4] whitespace-nowrap">
                <span className="absolute top-0 left-0 right-0 h-[2px] bg-amber-400" />
                <Film className="w-4 h-4 text-amber-400" />
                <span>DIC 動画フレーム抽出</span>
              </div>
            )}
          </div>

          <main className="flex-1 min-h-0 overflow-y-auto p-4 bg-[#0b0c0f]">
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
                  onFolderPickedByUser={() => setFolderPickSeq((s) => s + 1)}
                />
              ) : xrdStep === 2 ? (
                <Step2InitialPick
                  folderPath={folderPath}
                  specimenName={specimenName}
                  initialData={initialData}
                  setInitialData={setInitialData}
                  onConfirmInitialAndProceed={handleConfirmInitialAndProceed}
                  onSubScreenChange={setStep2SubScreen}
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
                  onPhysicsComputed={() => setPhysicsComputed(true)}
                />
              )}
            </div>
          </main>

          {showConsole && (
            <section className="h-[156px] shrink-0 bg-[#08090c] border-t border-[#22262f] flex flex-col min-h-0">
              <div className="h-8 px-3.5 border-b border-[#22262f] bg-[#101216] flex items-center justify-between text-[12px]">
                <div className="flex items-center gap-2 text-[#98a0ae] font-medium">
                  <Terminal className="w-3.5 h-3.5 text-sky-400" />
                  <span>ログ</span>
                  <span className="font-mono text-[11px] text-[#5d6473] tabular-nums">
                    {logs.length}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setLogs([])}
                    className="text-[11px] text-[#5d6473] hover:text-[#eef0f4]"
                  >
                    クリア
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowConsole(false)}
                    className="text-[11px] text-[#5d6473] hover:text-[#eef0f4]"
                  >
                    閉じる
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-3.5 py-2 font-mono text-[12px] space-y-1 tabular-nums">
                {logs.length === 0 ? (
                  <div className="text-[#5d6473]">空</div>
                ) : (
                  logs.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-2.5">
                      <span className="text-[#5d6473] shrink-0">{entry.time}</span>
                      <span
                        className={cn(
                          'shrink-0 uppercase text-[10px]',
                          entry.level === 'error'
                            ? 'text-rose-400'
                            : entry.level === 'warn'
                              ? 'text-amber-400'
                              : 'text-sky-400'
                        )}
                      >
                        {entry.level}
                      </span>
                      <span className="text-[#cfd4de] break-all">{entry.message}</span>
                    </div>
                  ))
                )}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* Status Bar (26px) */}
      <footer className="h-[26px] shrink-0 bg-[#101216] border-t border-[#252a35] px-3.5 flex items-center justify-between text-[11px] font-mono tabular-nums text-[#7c8494] select-none">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={cn(
              'font-sans font-semibold whitespace-nowrap',
              mainMode === 'xrd' ? 'text-sky-300' : 'text-amber-300'
            )}
          >
            {mainMode === 'xrd' ? `XRD 回折解析 ${xrdStep}/5` : 'DIC 動画フレーム抽出'}
          </span>
          {specimenName && (
            <span className="truncate max-w-[180px]" title={specimenName}>
              {specimenName}
            </span>
          )}
          {folderPath && (
            <span className="hidden md:inline truncate max-w-[360px]" title={folderPath}>
              {folderPath}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3.5 shrink-0">
          {hasBatchResults && (
            <button
              type="button"
              onClick={() => {
                setMainMode('xrd');
                setXrdStep(4);
              }}
              className={cn(
                'hover:underline whitespace-nowrap',
                totalOutlierCount > 0 ? 'text-amber-400' : 'text-emerald-400'
              )}
            >
              Outliers {totalOutlierCount}
            </button>
          )}
          <button
            type="button"
            onClick={handleToggleGuide}
            className="hover:text-sky-300 whitespace-nowrap font-sans"
          >
            {guideActive ? `Guide ${guideStepIndex + 1}/9` : 'Guide'}
          </button>
          <button
            type="button"
            onClick={() => setShowConsole((v) => !v)}
            className="hover:text-[#eef0f4] whitespace-nowrap"
          >
            Log {logs.length}
          </button>
          <span className="whitespace-nowrap">
            {isDesktopBridge() ? 'Desktop IPC' : 'Local API'}
          </span>
        </div>
      </footer>

      <WorkflowGuide
        active={guideActive}
        stepIndex={guideStepIndex}
        onStepChange={setGuideStepIndex}
        onNavigateTarget={handleNavigateFromGuide}
        onClose={handleCloseGuide}
        stateSnapshot={{
          mainMode,
          xrdStep,
          hasFolder: Boolean(folderPath.trim()),
          folderPickSeq,
          hasPreprocess: Boolean(preprocessResult),
          step2SubScreen,
          hasBatchConfigs: batchConfigs.length > 0,
          hasBatchResults,
          hasPhysicsResult: physicsComputed,
        }}
      />

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
