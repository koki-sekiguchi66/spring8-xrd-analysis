import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  BookOpen,
  Check,
  Command,
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
import { SegmentedControl } from './components/ui/SegmentedControl';

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
        done: Boolean(preprocessResult),
        indicator: preprocessResult ? ('done' as const) : null,
      },
      {
        step: 2 as XrdStep,
        label: '初期値',
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
        done: hasBatchResults,
        indicator: hasBatchResults ? ('done' as const) : null,
      },
      {
        step: 4 as XrdStep,
        label: '検証・出力',
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
        done: false,
        indicator: null,
      },
    ],
    [preprocessResult, initialData, batchConfigs.length, hasBatchResults, totalOutlierCount]
  );

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
      {/* Titlebar (36px) */}
      <header className="h-[36px] shrink-0 bg-[#101216] border-b border-[#22262f] px-2.5 flex items-center justify-between gap-2 select-none relative z-30">
        <div className="flex items-center gap-1 min-w-0">
          <div className="flex items-center gap-2 pr-2.5 mr-1 border-r border-[#22262f]">
            <div className="w-5 h-5 rounded bg-[#181c23] border border-[#2c313d] flex items-center justify-center shrink-0">
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
            <span className="text-[12px] font-semibold tracking-tight text-[#eef0f4] whitespace-nowrap">
              XRD AutoFit Studio
            </span>
          </div>

          <div className="hidden sm:flex items-center gap-0.5 text-[11px]">
            <div className="relative" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                onClick={() => setOpenMenu((m) => (m === 'file' ? null : 'file'))}
                className={cn(
                  'h-6 px-2 rounded transition-colors',
                  openMenu === 'file'
                    ? 'bg-[#1c2028] text-[#eef0f4]'
                    : 'text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#15181e]'
                )}
              >
                ファイル
              </button>
              {openMenu === 'file' && (
                <div className="absolute left-0 top-7 w-48 bg-[#15181e] border border-[#303644] rounded-md shadow-2xl py-1 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setOpenMenu(null);
                      handleSelectFolderQuick();
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    フォルダ選択...
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setOpenMenu(null);
                      setMainMode('xrd');
                      setXrdStep(1);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    前処理へ
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
                    ? 'bg-[#1c2028] text-[#eef0f4]'
                    : 'text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#15181e]'
                )}
              >
                表示
              </button>
              {openMenu === 'view' && (
                <div className="absolute left-0 top-7 w-52 bg-[#15181e] border border-[#303644] rounded-md shadow-2xl py-1 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setShowSidebar((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#cfd4de] hover:bg-[#1f242e] flex items-center justify-between"
                  >
                    <span>サイドバー</span>
                    <kbd className="text-[10px] font-mono text-[#5d6473]">Ctrl+B</kbd>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowConsole((v) => !v);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#cfd4de] hover:bg-[#1f242e] flex items-center justify-between"
                  >
                    <span>コンソール</span>
                    <kbd className="text-[10px] font-mono text-[#5d6473]">Ctrl+`</kbd>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowPalette(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#cfd4de] hover:bg-[#1f242e] flex items-center justify-between"
                  >
                    <span>コマンドパレット</span>
                    <kbd className="text-[10px] font-mono text-[#5d6473]">Ctrl+K</kbd>
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
                    ? 'bg-[#1c2028] text-[#eef0f4]'
                    : 'text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#15181e]'
                )}
              >
                ヘルプ
              </button>
              {openMenu === 'help' && (
                <div className="absolute left-0 top-7 w-48 bg-[#15181e] border border-[#303644] rounded-md shadow-2xl py-1 z-50">
                  <button
                    type="button"
                    onClick={() => {
                      setShowSpecModal(true);
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    モデル仕様
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      handleCheckHealth();
                      setOpenMenu(null);
                    }}
                    className="w-full px-3 py-1.5 text-left text-[11px] text-[#cfd4de] hover:bg-[#1f242e]"
                  >
                    API 接続確認
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowPalette(true)}
            className="hidden md:flex items-center justify-between gap-4 w-52 h-[24px] px-2.5 bg-[#08090c] border border-[#22262f] hover:border-[#303644] rounded text-[11px] text-[#5d6473] transition-colors"
          >
            <span className="flex items-center gap-1.5 truncate">
              <Search className="w-3 h-3 shrink-0" />
              <span className="truncate">検索 / コマンド...</span>
            </span>
            <kbd className="text-[10px] font-mono bg-[#15181e] border border-[#22262f] px-1 rounded text-[#858d9c] shrink-0">
              Ctrl+K
            </kbd>
          </button>

          <SegmentedControl<MainMode>
            ariaLabel="解析モード"
            size="sm"
            value={mainMode}
            onChange={setMainMode}
            options={[
              { value: 'xrd', label: 'XRD', accent: 'sky' },
              { value: 'dic', label: 'DIC', accent: 'emerald' },
            ]}
          />
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setShowSidebar((v) => !v)}
            title="サイドバー (Ctrl+B)"
            className={cn(
              'h-6 w-6 rounded flex items-center justify-center transition-colors',
              showSidebar
                ? 'bg-[#1c2028] text-[#eef0f4]'
                : 'text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#15181e]'
            )}
          >
            <PanelLeft className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setShowConsole((v) => !v)}
            title="コンソール (Ctrl+`)"
            className={cn(
              'h-6 w-6 rounded flex items-center justify-center transition-colors',
              showConsole
                ? 'bg-[#1c2028] text-[#eef0f4]'
                : 'text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#15181e]'
            )}
          >
            <PanelBottom className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setShowSpecModal(true)}
            title="仕様"
            className="h-6 px-1.5 rounded flex items-center gap-1 text-[11px] text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#15181e] transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">仕様</span>
          </button>
        </div>
      </header>

      {/* Main Workbench */}
      <div className="flex-1 min-h-0 flex">
        {/* Activity Rail (42px) */}
        <aside className="w-[42px] shrink-0 bg-[#101216] border-r border-[#22262f] flex flex-col items-center justify-between py-2 select-none">
          <div className="flex flex-col items-center gap-1 w-full">
            <button
              type="button"
              onClick={() => setMainMode('xrd')}
              title="XRD"
              className={cn(
                'relative w-full h-9 flex items-center justify-center transition-colors',
                mainMode === 'xrd' ? 'text-sky-400' : 'text-[#5d6473] hover:text-[#98a0ae]'
              )}
            >
              {mainMode === 'xrd' && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-sky-400 rounded-r" />
              )}
              <Layers className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={() => setMainMode('dic')}
              title="DIC"
              className={cn(
                'relative w-full h-9 flex items-center justify-center transition-colors',
                mainMode === 'dic' ? 'text-emerald-400' : 'text-[#5d6473] hover:text-[#98a0ae]'
              )}
            >
              {mainMode === 'dic' && (
                <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-emerald-400 rounded-r" />
              )}
              <Film className="w-4 h-4" />
            </button>
          </div>

          <div className="flex flex-col items-center gap-1 w-full">
            <button
              type="button"
              onClick={() => setShowPalette(true)}
              title="Ctrl+K"
              className="w-full h-8 flex items-center justify-center text-[#5d6473] hover:text-[#98a0ae]"
            >
              <Command className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setShowSpecModal(true)}
              title="仕様"
              className="w-full h-8 flex items-center justify-center text-[#5d6473] hover:text-[#98a0ae]"
            >
              <BookOpen className="w-3.5 h-3.5" />
            </button>
          </div>
        </aside>

        {/* Explorer Sidebar (216px) */}
        {showSidebar && (
          <aside className="w-[216px] shrink-0 bg-[#101216] border-r border-[#22262f] flex flex-col min-h-0 select-none">
            <div className="px-2.5 py-2 border-b border-[#22262f]">
              <button
                type="button"
                onClick={handleSelectFolderQuick}
                title={folderPath || 'フォルダ選択'}
                className="w-full px-2 py-1.5 rounded bg-[#08090c] border border-[#22262f] hover:border-[#303644] flex items-center justify-between gap-2 transition-colors text-left"
              >
                <div className="min-w-0">
                  <div className="text-[11px] font-medium text-[#eef0f4] truncate">
                    {specimenName || folderShortName}
                  </div>
                  <div className="text-[10px] font-mono text-[#5d6473] truncate">
                    {folderShortName}
                  </div>
                </div>
                <FolderOpen className="w-3.5 h-3.5 text-[#5d6473] shrink-0" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-1.5 py-2 space-y-0.5">
              {mainMode === 'xrd' ? (
                stepsMeta.map((item) => {
                  const isActive = item.step === xrdStep;
                  return (
                    <button
                      key={item.step}
                      type="button"
                      onClick={() => setXrdStep(item.step)}
                      className={cn(
                        'relative w-full h-8 px-2.5 rounded text-left flex items-center justify-between gap-2 transition-colors',
                        isActive
                          ? 'bg-[#181c23] text-[#eef0f4]'
                          : 'text-[#858d9c] hover:bg-[#14171d] hover:text-[#eef0f4]'
                      )}
                    >
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-sky-400 rounded-r" />
                      )}
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            'font-mono text-[10px] tabular-nums w-3.5 text-center shrink-0',
                            isActive ? 'text-sky-400' : 'text-[#5d6473]'
                          )}
                        >
                          {item.step}
                        </span>
                        <span className="text-[12px] font-medium truncate">{item.label}</span>
                      </div>

                      {item.indicator === 'done' ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                      ) : item.indicator ? (
                        <span
                          className={cn(
                            'text-[10px] font-mono tabular-nums px-1.5 rounded leading-4 shrink-0 whitespace-nowrap',
                            item.step === 4 && totalOutlierCount > 0
                              ? 'bg-amber-500/15 text-amber-300'
                              : 'bg-[#1d212a] text-[#98a0ae]'
                          )}
                        >
                          {item.indicator}
                        </span>
                      ) : null}
                    </button>
                  );
                })
              ) : (
                <div className="relative h-8 px-2.5 rounded bg-[#181c23] text-[#eef0f4] flex items-center gap-2">
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-[2px] bg-emerald-400 rounded-r" />
                  <Film className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="text-[12px] font-medium truncate">フレーム抽出</span>
                </div>
              )}
            </div>
          </aside>
        )}

        {/* Center Workbench Stage */}
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          {/* Flat Document Tab Strip (34px) */}
          <div className="h-[34px] shrink-0 bg-[#101216] border-b border-[#22262f] flex items-center overflow-x-auto select-none">
            {mainMode === 'xrd' ? (
              stepsMeta.map((item) => {
                const isActive = item.step === xrdStep;
                return (
                  <button
                    key={item.step}
                    type="button"
                    onClick={() => setXrdStep(item.step)}
                    className={cn(
                      'relative h-full px-3.5 text-[11px] font-medium flex items-center gap-1.5 border-r border-[#22262f] whitespace-nowrap transition-colors',
                      isActive
                        ? 'bg-[#0b0c0f] text-[#eef0f4]'
                        : 'bg-transparent text-[#858d9c] hover:text-[#eef0f4] hover:bg-[#15181e]'
                    )}
                  >
                    {isActive && (
                      <span className="absolute top-0 left-0 right-0 h-[2px] bg-sky-400" />
                    )}
                    <span className="font-mono text-[10px] text-[#5d6473]">{item.step}.</span>
                    <span>{item.label}</span>
                    {item.done && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />}
                    {item.step === 4 && totalOutlierCount > 0 && (
                      <span className="px-1 rounded bg-amber-500/15 text-amber-300 text-[10px] font-mono tabular-nums">
                        {totalOutlierCount}
                      </span>
                    )}
                  </button>
                );
              })
            ) : (
              <div className="relative h-full px-3.5 text-[11px] font-medium flex items-center gap-1.5 border-r border-[#22262f] bg-[#0b0c0f] text-[#eef0f4] whitespace-nowrap">
                <span className="absolute top-0 left-0 right-0 h-[2px] bg-emerald-400" />
                <Film className="w-3.5 h-3.5 text-emerald-400" />
                <span>フレーム抽出</span>
              </div>
            )}
          </div>

          <main className="flex-1 min-h-0 overflow-y-auto p-3.5 bg-[#0b0c0f]">
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

          {showConsole && (
            <section className="h-[156px] shrink-0 bg-[#08090c] border-t border-[#22262f] flex flex-col min-h-0">
              <div className="h-7 px-3 border-b border-[#22262f] bg-[#101216] flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-2 text-[#98a0ae] font-medium">
                  <Terminal className="w-3.5 h-3.5 text-sky-400" />
                  <span>ログ</span>
                  <span className="font-mono text-[10px] text-[#5d6473] tabular-nums">
                    {logs.length}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setLogs([])}
                    className="text-[10px] text-[#5d6473] hover:text-[#eef0f4]"
                  >
                    クリア
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowConsole(false)}
                    className="text-[10px] text-[#5d6473] hover:text-[#eef0f4]"
                  >
                    閉じる
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-3 py-1.5 font-mono text-[11px] space-y-0.5 tabular-nums">
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

      {/* Status Bar (22px) */}
      <footer className="h-[22px] shrink-0 bg-[#101216] border-t border-[#22262f] px-3 flex items-center justify-between text-[10px] font-mono tabular-nums text-[#5d6473] select-none">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-[#98a0ae] whitespace-nowrap">
            {mainMode === 'xrd' ? `XRD ${xrdStep}/5` : 'DIC'}
          </span>
          {specimenName && (
            <span className="truncate max-w-[160px]" title={specimenName}>
              {specimenName}
            </span>
          )}
          {folderPath && (
            <span className="hidden md:inline truncate max-w-[320px]" title={folderPath}>
              {folderPath}
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
                totalOutlierCount > 0 ? 'text-amber-400' : 'text-emerald-400'
              )}
            >
              Outliers {totalOutlierCount}
            </button>
          )}
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
