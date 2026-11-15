import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Play,
  Sliders,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  RefreshCw,
  LineChart,
  X,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { Button } from './ui/Button';
import { EmptyCanvas } from './ui/EmptyCanvas';
import { Panel, PanelBody, PanelHeader } from './ui/Panel';
import { SegmentedControl } from './ui/SegmentedControl';
import { PlotFrame } from './ui/PlotFrame';
import { CheckboxRow, FieldLabel, SelectInput, UnitNumberInput } from './ui/Field';
import { StatusBadge } from './ui/StatusBadge';
import { Notice } from './ui/Notice';
import { apiPost, fmtFixed, runFittingStream } from '../lib/utils';
import { applyInitialExcel, type InitialExcelData } from '../lib/initialExcel';
import { ENGINE_RUN_DEFAULTS, defaultLimitsFor } from '../lib/engineDefaults';
import type { BatchGroupResult, FitLimitConfig, GroupBatchConfig, PeakFitParam } from '../types/xrd';

export interface Step3BatchRunProps {
  folderPath: string;
  specimenName: string;
  initialExcelPath: string;
  batchConfigs: GroupBatchConfig[];
  setBatchConfigs: React.Dispatch<React.SetStateAction<GroupBatchConfig[]>>;
  batchResults: Record<string, BatchGroupResult>;
  setBatchResults: React.Dispatch<React.SetStateAction<Record<string, BatchGroupResult>>>;
  onProceedStep4: () => void;
}

interface LiveWaveformState {
  num: number;
  filename: string;
  group_id: string;
  peaks: string[];
  residual_rmse: number;
  relative_residual: number;
  x: number[];
  y_obs: number[];
  y_fit: number[];
  components: Record<string, number[]>;
}


export const Step3BatchRun: React.FC<Step3BatchRunProps> = ({
  folderPath,
  specimenName,
  initialExcelPath,
  batchConfigs,
  setBatchConfigs,
  batchResults,
  setBatchResults,
  onProceedStep4,
}) => {
  const [subScreen, setSubScreen] = useState<'config' | 'monitor'>(
    Object.keys(batchResults).length > 0 ? 'monitor' : 'config'
  );
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [completedAll, setCompletedAll] = useState<boolean>(Object.keys(batchResults).length > 0);
  const [savedOutputPath, setSavedOutputPath] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [loadedInitPath, setLoadedInitPath] = useState<string>('');
  const [initLoadMsg, setInitLoadMsg] = useState<string | null>(null);

  const [activeGroupId, setActiveGroupId] = useState<string>(
    batchConfigs[0]?.group_id ?? ''
  );
  const [progressInfo, setProgressInfo] = useState<{
    groupId: string;
    groupIndex: number;
    totalGroups: number;
    completedFiles: number;
    totalFiles: number;
    progressPct: number;
    currentNum: number;
    relativeResidual: number;
  } | null>(null);

  const [liveRowsByGroup, setLiveRowsByGroup] = useState<Record<string, Record<string, number>[]>>({});
  const [liveWaveform, setLiveWaveform] = useState<LiveWaveformState | null>(null);

  // Harada's procedure: the initial values come from `_initial.xlsx` (the file saved in Step 2, or
  // one chosen here). It is read on entering Step 3 and read again at run time, so values edited in
  // Excel / Origin after Step 2 are used.
  const [initData, setInitData] = useState<InitialExcelData | null>(null);
  const activeInitPath = loadedInitPath || initialExcelPath;

  const loadInitialExcel = async (path: string, configs: GroupBatchConfig[]): Promise<GroupBatchConfig[]> => {
    const data = await apiPost<InitialExcelData>('/api/initial/load-excel', { excel_path: path });
    const res = applyInitialExcel(configs, data);
    setInitData(data);
    setBatchConfigs(res.configs);
    const parts = [`初期値ファイルから ${res.applied.length} 群に適用`];
    if (res.skipped.length) parts.push(`Step2 の値を使用: ${res.skipped.map((x) => `${x.group_id} (${x.reason})`).join(' / ')}`);
    if (res.warnings.length) parts.push(res.warnings.join(' / '));
    setInitLoadMsg(parts.join(' · '));
    return res.configs;
  };

  const autoLoadedRef = useRef<string>('');
  useEffect(() => {
    if (!initialExcelPath || loadedInitPath || autoLoadedRef.current === initialExcelPath) return;
    if (batchConfigs.length === 0 || Object.keys(batchResults).length > 0) return;
    autoLoadedRef.current = initialExcelPath;
    loadInitialExcel(initialExcelPath, batchConfigs).catch((e: any) =>
      setError(`初期値ファイルの読込エラー: ${e.message || e}`)
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialExcelPath, batchConfigs.length]);

  /** Choose another Origin / Harada `_initial.xlsx` and use it from now on. */
  const handleLoadInitialExcel = async () => {
    setError(null);
    try {
      const pick = await apiPost<{ selected_path?: string; path?: string; cancelled?: boolean }>(
        '/api/dialog/select',
        { mode: 'excel_file', title: '初期値 Excel 選択', initial_dir: folderPath || undefined }
      );
      const picked = pick.selected_path || pick.path;
      if (pick.cancelled || !picked) return;
      await loadInitialExcel(picked, batchConfigs);
      setLoadedInitPath(picked);
    } catch (e: any) {
      setError(e.message || '初期値 Excel の読込エラー');
    }
  };

  const updateGroupConfig = (groupId: string, patch: Partial<GroupBatchConfig>) => {
    setBatchConfigs((prev) =>
      prev.map((cfg) => (cfg.group_id === groupId ? { ...cfg, ...patch } : cfg))
    );
  };

  /** Initial frame for an engine: 2PeaksRatio needs a pre-onset frame, 3PeaksLuders a post-onset one. */
  const pickInitFor = (
    cfg: GroupBatchConfig,
    engine: GroupBatchConfig['engine']
  ): Partial<GroupBatchConfig> => {
    const opts = cfg.init_options;
    if (!opts) return {};
    if (engine !== '2PeaksRatio' && engine !== '3PeaksLuders') {
      // back to the Step 2 frame
      const n0 = cfg.step2_num;
      return n0 !== undefined && opts[String(n0)] ? { init_num: n0, init_peaks: opts[String(n0)] } : {};
    }
    const nums = Object.keys(opts)
      .map(Number)
      .sort((a, b) => b - a);
    const onset = cfg.dimt_onset_num;
    const n =
      engine === '2PeaksRatio' ? nums.find((v) => v <= onset) : nums.find((v) => v >= onset);
    if (n === undefined) return {};
    const peaks = opts[String(n)];
    const patch: Partial<GroupBatchConfig> = { init_num: n, init_peaks: peaks };
    if (engine === '2PeaksRatio' && peaks.length > 1 && peaks[0].A > 0) {
      patch.R = Number((peaks[1].A / peaks[0].A).toFixed(4));
    }
    return patch;
  };

  /** Harada's cold-rolled flow: 2PeaksRatio (num <= onset) + 3PeaksLuders (num >= onset, R = best_R). */
  const addLudersGroup = async (cfg: GroupBatchConfig) => {
    const id = `${cfg.group_id}_luders`;
    if (batchConfigs.some((c) => c.group_id === id)) return;
    const base: GroupBatchConfig = {
      ...cfg,
      group_id: id,
      engine: '3PeaksLuders',
      peaks: ['fcc111a', 'bcc110a', 'bcc1102'],
      R_source_group: cfg.group_id,
      ...ENGINE_RUN_DEFAULTS['3PeaksLuders'],
      default_fit_limits: undefined,
    };
    let next: GroupBatchConfig = { ...base, ...pickInitFor(base, '3PeaksLuders') };
    // As in Harada's procedure: 3-peak Origin fit of a post-onset frame written to `_initial.xlsx`
    if (activeInitPath && next.init_num >= next.dimt_onset_num && next.init_peaks.length === 2) {
      try {
        const res = await apiPost<{ num: number; peaks: PeakFitParam[]; appended: boolean }>(
          '/api/initial/luders-block',
          {
            folder_path: folderPath,
            excel_path: activeInitPath,
            num: next.init_num,
            base_peaks: next.init_peaks,
            range_min: next.th_min,
            range_max: next.th_max,
            v3_center_cap: next.v3_center_cap ?? 11.65,
          }
        );
        next = { ...next, init_num: res.num, init_peaks: res.peaks };
        const data = await apiPost<InitialExcelData>('/api/initial/load-excel', { excel_path: activeInitPath });
        setInitData(data);
        setInitLoadMsg(
          `${id}: 3 ピーク初期値 (No ${res.num}) を${res.appended ? '初期値ファイルに追加' : '初期値ファイルから使用'}`
        );
      } catch (e: any) {
        setError(`Lüders 初期値の作成エラー: ${e.message || e}`);
      }
    }
    setBatchConfigs((prev) => [...prev, next]);
  };

  const updatePeakLimit = (
    groupId: string,
    peakIdx: number,
    field: keyof FitLimitConfig,
    value: number
  ) => {
    setBatchConfigs((prev) =>
      prev.map((cfg) => {
        if (cfg.group_id !== groupId) return cfg;
        const vKey = `v${peakIdx + 1}`;
        const existingLimits = cfg.default_fit_limits || {};
        const curPeakLimit = existingLimits[vKey] || defaultLimitsFor(cfg.engine, peakIdx);
        return {
          ...cfg,
          default_fit_limits: {
            ...existingLimits,
            [vKey]: {
              ...curPeakLimit,
              [field]: value,
            },
          },
        };
      })
    );
  };

  const handleStartBatchRun = async () => {
    if (batchConfigs.length === 0) {
      setError('解析対象グループがありません。Step 2 でピークを選択してください。');
      return;
    }

    let runConfigs = batchConfigs;
    if (activeInitPath) {
      try {
        runConfigs = await loadInitialExcel(activeInitPath, batchConfigs);
      } catch (e: any) {
        setError(`初期値ファイルを読めないため中止しました: ${e.message || e}`);
        return;
      }
    }

    setRunning(true);
    setCompletedAll(false);
    setError(null);
    setLiveRowsByGroup({});
    setSubScreen('monitor');
    if (batchConfigs[0]) {
      setActiveGroupId(batchConfigs[0].group_id);
    }

    try {
      await runFittingStream(
        {
          folder_path: folderPath,
          specimen_name: specimenName,
          groups: runConfigs,
        },
        (rawMsg) => {
          const msg = rawMsg as Record<string, any>;
          if (msg.type === 'group_start') {
            setActiveGroupId(msg.group_id);
            setProgressInfo({
              groupId: msg.group_id,
              groupIndex: msg.group_index + 1,
              totalGroups: msg.total_groups,
              completedFiles: 0,
              totalFiles: msg.total_files,
              progressPct: 0,
              currentNum: 0,
              relativeResidual: 0,
            });
          } else if (msg.type === 'step') {
            setProgressInfo({
              groupId: msg.group_id,
              groupIndex: msg.group_index + 1,
              totalGroups: msg.total_groups,
              completedFiles: msg.completed_files,
              totalFiles: msg.total_files,
              progressPct: msg.progress_pct,
              currentNum: msg.num,
              relativeResidual: msg.relative_residual,
            });
            setLiveRowsByGroup((prev) => {
              const curList = prev[msg.group_id] ? [...prev[msg.group_id]] : [];
              curList.push(msg.row_data);
              curList.sort((a, b) => Number(a.num) - Number(b.num));
              return { ...prev, [msg.group_id]: curList };
            });
            if (msg.waveform) {
              setLiveWaveform({
                num: msg.num,
                filename: msg.filename,
                group_id: msg.group_id,
                peaks: msg.peaks,
                residual_rmse: msg.residual_rmse,
                relative_residual: msg.relative_residual,
                x: msg.waveform.x,
                y_obs: msg.waveform.y_obs,
                y_fit: msg.waveform.y_fit,
                components: msg.waveform.components,
              });
            }
          } else if (msg.type === 'group_complete') {
            const summary: BatchGroupResult = msg.group_summary;
            setBatchResults((prev) => ({ ...prev, [summary.group_id]: summary }));
            setLiveRowsByGroup((prev) => ({ ...prev, [summary.group_id]: summary.rows }));
          } else if (msg.type === 'all_complete') {
            setBatchResults(msg.groups);
            if (msg.saved_output_path) {
              setSavedOutputPath(msg.saved_output_path);
            }
            setRunning(false);
            setCompletedAll(true);
          } else if (msg.type === 'error') {
            setError(msg.detail || '連続フィッティング中にエラーが発生しました');
            setRunning(false);
          }
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  const activeGroupConfig = useMemo(
    () => batchConfigs.find((g) => g.group_id === activeGroupId) ?? batchConfigs[0],
    [batchConfigs, activeGroupId]
  );

  const activeRows = useMemo(() => {
    if (batchResults[activeGroupId]?.rows) {
      return batchResults[activeGroupId].rows;
    }
    return liveRowsByGroup[activeGroupId] ?? [];
  }, [batchResults, liveRowsByGroup, activeGroupId]);

  const activeGroupPeaks = useMemo(() => {
    if (batchResults[activeGroupId]?.peaks) {
      return batchResults[activeGroupId].peaks;
    }
    return activeGroupConfig?.peaks ?? [];
  }, [batchResults, activeGroupConfig, activeGroupId]);

  const waveformTraces = useMemo(() => {
    if (!liveWaveform) return [];
    const traces: Record<string, unknown>[] = [
      {
        x: liveWaveform.x,
        y: liveWaveform.y_obs,
        type: 'scatter',
        mode: 'markers',
        name: `#${liveWaveform.num}`,
        marker: { color: '#9ca3b0', size: 4.5 },
      },
      {
        x: liveWaveform.x,
        y: liveWaveform.y_fit,
        type: 'scatter',
        mode: 'lines',
        name: '合成Voigt',
        line: { color: '#f43f5e', width: 2.2 },
      },
    ];
    for (const pk of liveWaveform.peaks) {
      const comp = liveWaveform.components?.[pk];
      if (comp) {
        const isGamma = pk.startsWith('fcc');
        traces.push({
          x: liveWaveform.x,
          y: comp,
          type: 'scatter',
          mode: 'lines',
          name: pk,
          line: {
            color: isGamma ? '#38bdf8' : '#f59e0b',
            width: 1.8,
            dash: 'dot',
          },
        });
      }
    }
    return traces;
  }, [liveWaveform]);

  const trend2thTraces = useMemo(() => {
    if (!activeRows.length) return [];
    return activeGroupPeaks.map((pk) => {
      const isGamma = pk.startsWith('fcc');
      return {
        x: activeRows.map((r) => r.num),
        y: activeRows.map((r) => r[`2th_${pk}`]),
        type: 'scatter',
        mode: 'markers+lines',
        name: `2θ_${pk}`,
        marker: { color: isGamma ? '#38bdf8' : '#f59e0b', size: 4.5 },
        line: { color: isGamma ? '#38bdf8' : '#f59e0b', width: 1.4 },
      };
    });
  }, [activeRows, activeGroupPeaks]);

  const trendAreaTraces = useMemo(() => {
    if (!activeRows.length) return [];
    return activeGroupPeaks.map((pk) => {
      const isGamma = pk.startsWith('fcc');
      return {
        x: activeRows.map((r) => r.num),
        y: activeRows.map((r) => r[`I_${pk}`]),
        type: 'scatter',
        mode: 'markers+lines',
        name: `I_${pk}`,
        marker: { color: isGamma ? '#38bdf8' : '#f59e0b', size: 4.5 },
        line: { color: isGamma ? '#38bdf8' : '#f59e0b', width: 1.4 },
      };
    });
  }, [activeRows, activeGroupPeaks]);

  const trendFwhmTraces = useMemo(() => {
    if (!activeRows.length) return [];
    return activeGroupPeaks.map((pk) => {
      const isGamma = pk.startsWith('fcc');
      return {
        x: activeRows.map((r) => r.num),
        y: activeRows.map((r) => r[`FWHM_${pk}`]),
        type: 'scatter',
        mode: 'markers+lines',
        name: `FWHM_${pk}`,
        marker: { color: isGamma ? '#38bdf8' : '#f59e0b', size: 4.5 },
        line: { color: isGamma ? '#38bdf8' : '#f59e0b', width: 1.4 },
      };
    });
  }, [activeRows, activeGroupPeaks]);

  return (
    <div className="space-y-4">
      {/* Action & View Toolbar */}
      <Panel>
        <div className="px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <SegmentedControl
              ariaLabel="表示切替"
              size="md"
              value={subScreen}
              onChange={setSubScreen}
              options={[
                {
                  value: 'config',
                  label: '設定',
                  icon: <Sliders className="size-4" aria-hidden="true" />,
                  accent: 'sky',
                },
                {
                  value: 'monitor',
                  label: 'モニター',
                  icon: <LineChart className="size-4" aria-hidden="true" />,
                  accent: 'sky',
                },
              ]}
            />

            {savedOutputPath ? (
              <span className="text-[12px] font-mono text-emerald-300 truncate max-w-md">
                {savedOutputPath}
              </span>
            ) : loadedInitPath || initialExcelPath ? (
              <span className="text-[12px] font-mono text-[#7c8494] truncate max-w-md">
                {loadedInitPath || initialExcelPath}
              </span>
            ) : null}
          </div>

          <div className="flex items-center gap-2.5">
            <Button variant="secondary" size="md" disabled={running} onClick={handleLoadInitialExcel}>
              初期値 Excel
            </Button>
            <Button
              data-guide="step3-run"
              variant="primary"
              size="md"
              disabled={running}
              onClick={handleStartBatchRun}
            >
              {running ? (
                <>
                  <RefreshCw className="size-4 animate-spin" aria-hidden="true" />
                  <span>実行中...</span>
                </>
              ) : (
                <>
                  <Play className="size-4 fill-current" aria-hidden="true" />
                  <span>一括実行 ({batchConfigs.length})</span>
                </>
              )}
            </Button>

            {completedAll && (
              <Button data-guide="step3-next" variant="emerald" size="md" onClick={onProceedStep4}>
                <span>次へ: 検証</span>
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        </div>
      </Panel>

      {error && <Notice tone="error">{error}</Notice>}
      {initLoadMsg && <Notice tone="info">{initLoadMsg}</Notice>}

      {/* Slim Progress Strip */}
      {progressInfo && (
        <Panel className="px-4 py-2.5 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono tabular-nums">
            <div className="flex items-center gap-2">
              <StatusBadge tone="sky" dot>
                {progressInfo.groupIndex}/{progressInfo.totalGroups} {progressInfo.groupId}
              </StatusBadge>
              <span className="text-[#9ca3b0]">#{progressInfo.currentNum}</span>
            </div>
            <div className="flex items-center gap-4 text-[#9ca3b0]">
              <span>
                進捗{' '}
                <strong className="text-[#eceef2]">
                  {progressInfo.completedFiles}/{progressInfo.totalFiles} (
                  {fmtFixed(progressInfo.progressPct, 1)}%)
                </strong>
              </span>
              <span>
                相対残差{' '}
                <strong className="text-emerald-300">
                  {fmtFixed(progressInfo.relativeResidual, 4)}
                </strong>
              </span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-[#0a0b0e] rounded-full overflow-hidden border border-[#23262e]">
            <div
              className="h-full bg-sky-400 origin-left transition-transform duration-150 ease-out"
              style={{
                transform: `scaleX(${Math.min(1, Math.max(0, progressInfo.progressPct / 100))})`,
              }}
            />
          </div>
        </Panel>
      )}

      {/* SUB-SCREEN 1: Group Engine & Constraint Config */}
      {subScreen === 'config' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-start">
          {batchConfigs.length === 0 ? (
            <EmptyCanvas
              className="md:col-span-2 h-72"
              label="グループ未選択"
              meta="Step 2"
            />
          ) : (
            batchConfigs.map((cfg) => {
              const isExpanded = expandedGroupId === cfg.group_id;
              const isMulti = cfg.peaks.length > 1;
              return (
                <Panel
                  key={cfg.group_id}
                  className={
                    activeGroupId === cfg.group_id ? 'border-sky-500/45' : undefined
                  }
                >
                  <div className="px-3.5 py-2.5 flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => setActiveGroupId(cfg.group_id)}
                      className="text-left flex items-center gap-2 min-w-0"
                    >
                      <span className="text-[13px] font-mono font-semibold text-[#eceef2] truncate">
                        {cfg.peaks.join(' + ')}
                      </span>
                      <StatusBadge tone="neutral" mono>
                        #{cfg.init_num}
                      </StatusBadge>
                    </button>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <SelectInput
                        aria-label={`${cfg.group_id} 解析エンジン`}
                        mono
                        value={cfg.engine}
                        onChange={(e) => {
                          const engine = e.target.value as GroupBatchConfig['engine'];
                          // Switch to the residual criterion and per-frame limits of that engine's original script
                          const switched: GroupBatchConfig = {
                            ...cfg,
                            engine,
                            ...ENGINE_RUN_DEFAULTS[engine],
                            default_fit_limits: undefined,
                          };
                          const fromFile = initData
                            ? applyInitialExcel([switched], initData)
                            : null;
                          updateGroupConfig(
                            cfg.group_id,
                            fromFile && fromFile.applied.length
                              ? fromFile.configs[0]
                              : { ...switched, ...pickInitFor(cfg, engine) }
                          );
                        }}
                        className="w-40 h-7 text-xs"
                      >
                        {isMulti ? (
                          <>
                            <option value="MultiPeaks">MultiPeaks</option>
                            <option value="2PeaksRatio">2PeaksRatio</option>
                            <option value="3PeaksLuders">3PeaksLuders</option>
                          </>
                        ) : (
                          <option value="1Peak">1Peak</option>
                        )}
                      </SelectInput>

                      <Button
                        variant="ghost"
                        size="xs"
                        aria-expanded={isExpanded}
                        aria-label={`${cfg.group_id} 詳細パラメータ`}
                        onClick={() =>
                          setExpandedGroupId(isExpanded ? null : cfg.group_id)
                        }
                        className="px-1.5"
                      >
                        {isExpanded ? (
                          <ChevronUp className="size-4" aria-hidden="true" />
                        ) : (
                          <ChevronDown className="size-4" aria-hidden="true" />
                        )}
                      </Button>
                      {cfg.R_source_group && (
                        <Button
                          variant="ghost"
                          size="xs"
                          aria-label={`${cfg.group_id} を削除`}
                          onClick={() =>
                            setBatchConfigs((prev) => prev.filter((c) => c.group_id !== cfg.group_id))
                          }
                          className="px-1.5"
                        >
                          <X className="size-4" aria-hidden="true" />
                        </Button>
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-[#23262e] p-3.5 space-y-3 bg-[#121418]">
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                        <div>
                          <FieldLabel>最小角度 th_min</FieldLabel>
                          <UnitNumberInput
                            step="0.05"
                            unit="deg"
                            value={cfg.th_min ?? 11.0}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, { th_min: Number(e.target.value) })
                            }
                          />
                        </div>
                        <div>
                          <FieldLabel>最大角度 th_max</FieldLabel>
                          <UnitNumberInput
                            step="0.05"
                            unit="deg"
                            value={cfg.th_max ?? 12.1}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, { th_max: Number(e.target.value) })
                            }
                          />
                        </div>
                        <div>
                          <FieldLabel>残差許容値</FieldLabel>
                          <UnitNumberInput
                            step="0.1"
                            value={cfg.residual_limit}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, {
                                residual_limit: Number(e.target.value),
                              })
                            }
                          />
                        </div>
                        <div>
                          <FieldLabel>再試行上限</FieldLabel>
                          <UnitNumberInput
                            step="1"
                            value={cfg.max_attempts}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, {
                                max_attempts: Number(e.target.value),
                              })
                            }
                          />
                        </div>
                        <div>
                          <FieldLabel>変態開始 num</FieldLabel>
                          <UnitNumberInput
                            step="10"
                            value={cfg.dimt_onset_num}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, {
                                dimt_onset_num: Number(e.target.value),
                              })
                            }
                          />
                        </div>
                        {cfg.engine === '3PeaksLuders' && (
                          <div>
                            <FieldLabel>
                              {cfg.R_source_group
                                ? `R (実行時に ${cfg.R_source_group} の best_R を使用)`
                                : '強度比 R (2PeaksRatio の best_R)'}
                            </FieldLabel>
                            <UnitNumberInput
                              step="0.02"
                              value={cfg.R}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, { R: Number(e.target.value) })
                              }
                            />
                          </div>
                        )}
                      </div>

                      {cfg.engine === '2PeaksRatio' && (
                        <Notice tone="info">
                          冷間圧延材 (ver10): num ≤ 変態開始のみ前向き解析・R 粗→細探索。初期値は変態前ファイル
                          (#{cfg.init_num})
                          {!batchConfigs.some((c) => c.group_id === `${cfg.group_id}_luders`) && (
                            <>
                              {' '}
                              <button
                                type="button"
                                className="underline underline-offset-2 hover:text-sky-100 transition-colors duration-150"
                                onClick={() => addLudersGroup(cfg)}
                              >
                                変態後の 3PeaksLuders 群を追加 (R = best_R)
                              </button>
                            </>
                          )}
                        </Notice>
                      )}
                      {cfg.engine === '3PeaksLuders' && (
                        <Notice tone="info">
                          冷間圧延材 (ver4): num ≥ 変態開始のみ解析。初期値は変態後ファイル
                        </Notice>
                      )}

                      <CheckboxRow
                        checked={cfg.fit_y0 ?? false}
                        onChange={(val) => updateGroupConfig(cfg.group_id, { fit_y0: val })}
                        label={
                          <span className="text-xs">
                            定数背景 y0 を fit (任意・原田法外: 背景除去後の残留背景が大きい時)
                          </span>
                        }
                      />

                      {cfg.peaks.some((pk) => pk === 'bcc110' || pk === 'bcc101') && (
                        <div className="p-2.5 rounded-md bg-[#0a0b0e] border border-amber-500/35 space-y-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <CheckboxRow
                              checked={cfg.use_bcc211_constraint ?? false}
                              onChange={(val) =>
                                updateGroupConfig(cfg.group_id, {
                                  use_bcc211_constraint: val,
                                })
                              }
                              label={
                                <span className="text-xs font-medium text-amber-200">
                                  bcc211 拘束 (任意・原田法外)
                                </span>
                              }
                            />
                            {(cfg.use_bcc211_constraint ?? false) && (
                              <div className="flex items-center gap-1.5">
                                <span className="text-[11px] font-mono text-[#9ca3b0]">Δθ_tol</span>
                                <UnitNumberInput
                                  step="0.01"
                                  min="0.005"
                                  max="0.30"
                                  unit="deg"
                                  value={cfg.bcc110_center_tol_deg ?? 0.05}
                                  onChange={(e) =>
                                    updateGroupConfig(cfg.group_id, {
                                      bcc110_center_tol_deg: Number(e.target.value),
                                    })
                                  }
                                  className="w-28"
                                />
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {cfg.engine === '3PeaksLuders' && (
                        <div className="grid grid-cols-3 gap-2.5 pt-2 border-t border-[#23262e]">
                          <div>
                            <FieldLabel>undeform_initial</FieldLabel>
                            <UnitNumberInput
                              value={cfg.undeform_initial}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, {
                                  undeform_initial: Number(e.target.value),
                                })
                              }
                            />
                          </div>
                          <div>
                            <FieldLabel>undeform_end</FieldLabel>
                            <UnitNumberInput
                              value={cfg.undeform_end}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, {
                                  undeform_end: Number(e.target.value),
                                })
                              }
                            />
                          </div>
                          <div>
                            <FieldLabel>第3ピーク比 R2</FieldLabel>
                            <UnitNumberInput
                              step="0.1"
                              value={cfg.R2}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, { R2: Number(e.target.value) })
                              }
                            />
                          </div>
                        </div>
                      )}

                      <div className="pt-2 border-t border-[#23262e] space-y-2">
                        <div className="text-xs font-medium text-[#9ca3b0]">
                          ステップ追従拘束 (default_fit_limits)
                        </div>
                        {cfg.peaks.map((pkName, pkIdx) => {
                          const vKey = `v${pkIdx + 1}`;
                          const lim =
                            cfg.default_fit_limits?.[vKey] || defaultLimitsFor(cfg.engine, pkIdx);
                          return (
                            <div
                              key={pkName}
                              className="p-2.5 rounded-md bg-[#0a0b0e] border border-[#23262e] space-y-2"
                            >
                              <div className="text-[11px] font-mono text-sky-300 font-semibold">
                                {vKey}: {pkName}
                              </div>
                              <div className="grid grid-cols-4 gap-2 text-[11px]">
                                {(
                                  [
                                    ['center_min_offset', 'c_min', 0.005],
                                    ['center_max_offset', 'c_max', 0.005],
                                    ['amplitude_min_factor', 'A_min', 0.05],
                                    ['amplitude_max_factor', 'A_max', 0.05],
                                    ['sigma_min_factor', 'σ_min', 0.05],
                                    ['sigma_max_factor', 'σ_max', 0.05],
                                    ['gamma_min_factor', 'γ_min', 0.05],
                                    ['gamma_max_factor', 'γ_max', 0.05],
                                  ] as const
                                ).map(([fieldKey, shortLabel, stepVal]) => (
                                  <div key={fieldKey}>
                                    <span className="text-[#636b78] font-mono block mb-0.5">
                                      {shortLabel}
                                    </span>
                                    <input
                                      type="number"
                                      step={stepVal}
                                      value={lim[fieldKey]}
                                      onChange={(e) =>
                                        updatePeakLimit(
                                          cfg.group_id,
                                          pkIdx,
                                          fieldKey,
                                          Number(e.target.value)
                                        )
                                      }
                                      className="w-full h-7 bg-[#16181d] border border-[#2a2e38] rounded px-1.5 font-mono tabular-nums text-[#eceef2] focus:border-sky-500/70 focus:outline-none"
                                    />
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </Panel>
              );
            })
          )}
        </div>
      )}

      {/* SUB-SCREEN 2: Real-Time Waveform & Trend Monitor */}
      {subScreen === 'monitor' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
            <PlotFrame
            className="lg:col-span-5"
            title="波形フィット"
            subtitle={liveWaveform ? `#${liveWaveform.num} (${liveWaveform.filename})` : undefined}
          >
            {liveWaveform ? (
              <PlotlyChart
                data={waveformTraces}
                layout={{
                  margin: { l: 50, r: 14, t: 14, b: 38 },
                  xaxis: { title: '2θ (deg)' },
                  yaxis: { title: 'Intensity (a.u.)' },
                }}
                className="w-full h-[460px]"
              />
            ) : (
              <EmptyCanvas className="h-[460px]" label="実行待機中" />
            )}
          </PlotFrame>

          <Panel className="lg:col-span-7">
            <PanelHeader
              title="パラメータ推移"
              actions={
                <div className="flex flex-wrap items-center gap-1">
                  {batchConfigs.map((cfg) => (
                    <button
                      key={cfg.group_id}
                      type="button"
                      onClick={() => setActiveGroupId(cfg.group_id)}
                      className={`h-6 px-2 rounded text-xs font-mono border transition-colors ${
                        activeGroupId === cfg.group_id
                          ? 'bg-sky-500/15 border-sky-500/50 text-sky-300 font-semibold'
                          : 'bg-[#0a0b0e] border-[#23262e] text-[#9ca3b0] hover:text-[#eceef2]'
                      }`}
                    >
                      {cfg.peaks.join('+')}
                    </button>
                  ))}
                </div>
              }
            />
            <PanelBody className="space-y-2.5 p-3">
              <div className="rounded-md bg-[#0a0b0e] border border-[#23262e] p-1.5">
                <PlotlyChart
                  data={trend2thTraces}
                  layout={{
                    margin: { l: 56, r: 14, t: 18, b: 28 },
                    xaxis: { title: '' },
                    yaxis: { title: '2θ (deg)' },
                  }}
                  className="w-full h-36"
                />
              </div>
              <div className="rounded-md bg-[#0a0b0e] border border-[#23262e] p-1.5">
                <PlotlyChart
                  data={trendAreaTraces}
                  layout={{
                    margin: { l: 56, r: 14, t: 18, b: 28 },
                    xaxis: { title: '' },
                    yaxis: { title: '面積強度 I' },
                  }}
                  className="w-full h-36"
                />
              </div>
              <div className="rounded-md bg-[#0a0b0e] border border-[#23262e] p-1.5">
                <PlotlyChart
                  data={trendFwhmTraces}
                  layout={{
                    margin: { l: 56, r: 14, t: 18, b: 36 },
                    xaxis: { title: 'num' },
                    yaxis: { title: 'FWHM (deg)' },
                  }}
                  className="w-full h-36"
                />
              </div>
            </PanelBody>
          </Panel>
        </div>
      )}
    </div>
  );
};
