import React, { useMemo, useState } from 'react';
import {
  Play,
  Sliders,
  ChevronDown,
  ChevronUp,
  Activity,
  CheckCircle2,
  ArrowRight,
  AlertCircle,
  RefreshCw,
  LineChart,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { TutorialGuideBanner } from './TutorialGuideBanner';
import { fmtFixed, runFittingStream } from '../lib/utils';
import type { BatchGroupResult, FitLimitConfig, GroupBatchConfig } from '../types/xrd';

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

const DEFAULT_LIMIT_TEMPLATE: FitLimitConfig = {
  center_min_offset: -0.05,
  center_max_offset: 0.2,
  amplitude_min_factor: 0.8,
  amplitude_max_factor: 1.25,
  amplitude_min_offset: 0,
  amplitude_max_offset: 10,
  sigma_min_factor: 0.7,
  sigma_max_factor: 1.4,
  sigma_min_offset: 0,
  sigma_max_offset: 0.0001,
  gamma_min_factor: 0.7,
  gamma_max_factor: 1.4,
  gamma_min_offset: 0,
  gamma_max_offset: 0.0001,
};

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

  const updateGroupConfig = (groupId: string, patch: Partial<GroupBatchConfig>) => {
    setBatchConfigs((prev) =>
      prev.map((cfg) => (cfg.group_id === groupId ? { ...cfg, ...patch } : cfg))
    );
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
        const curPeakLimit = existingLimits[vKey] || { ...DEFAULT_LIMIT_TEMPLATE };
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
      setError('解析対象のグループが設定されていません。Step 2に戻って選択してください。');
      return;
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
          groups: batchConfigs,
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
            setError(msg.detail || 'Batch fitting error');
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
        name: `実測 (#${liveWaveform.num})`,
        marker: { color: '#a1a1aa', size: 5 },
      },
      {
        x: liveWaveform.x,
        y: liveWaveform.y_fit,
        type: 'scatter',
        mode: 'lines',
        name: '合成Voigt',
        line: { color: '#f43f5e', width: 2.5 },
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
            color: isGamma ? '#06b6d4' : '#f59e0b',
            width: 2,
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
        marker: { color: isGamma ? '#06b6d4' : '#f59e0b', size: 5 },
        line: { color: isGamma ? '#06b6d4' : '#f59e0b', width: 1.5 },
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
        marker: { color: isGamma ? '#06b6d4' : '#f59e0b', size: 5 },
        line: { color: isGamma ? '#06b6d4' : '#f59e0b', width: 1.5 },
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
        marker: { color: isGamma ? '#06b6d4' : '#f59e0b', size: 5 },
        line: { color: isGamma ? '#06b6d4' : '#f59e0b', width: 1.5 },
      };
    });
  }, [activeRows, activeGroupPeaks]);

  return (
    <div className="space-y-6">
      <TutorialGuideBanner
        mode="xrd"
        stepTitle="Step 3: 全ファイル連続Voigtフィッティング ＆ リアルタイム監視"
        summary="Step 2で確定した初期値を起点に、全フレームのX線回折データを自動で連続フィッティングします。そのまま「全ファイル連続解析スタート」を押すだけで実行でき、実行中はリアルタイムモニター画面に自動遷移します。"
        steps={[
          {
            badge: 'STEP 1',
            title: 'エンジンの確認（そのままでOK）',
            description: '単一ピークは「1Peak」、γ+α\'重畳ペアは「2PeaksRatio」が自動選択されています。',
          },
          {
            badge: 'STEP 2',
            title: '「全ファイル連続解析スタート」をクリック',
            description: '双方向トラッキング（初期値番号から前後へ追跡）により、ピークシフトに追従しながら連続計算します。',
          },
          {
            badge: 'STEP 3',
            title: '完了後に「Step 4: 要確認フィット一括検証へ進む」をクリック',
            description: '全フレーム完了後、外れ値の確認・一括再フィット画面へ進みます。',
          },
        ]}
        glossary={[
          {
            term: '双方向トラッキング (Bidirectional Tracking)',
            meaning:
              '初期値を取得したファイル番号（例: #900）から番号が減る方向（#900→#10）と増える方向（#900→最後）の両方向に向かって、直前フレームのフィット結果を次の初期値として引き継ぐ手法です。',
          },
          {
            term: '積分強度スケーリング',
            meaning:
              '結晶粒回転や集合組織変化で回折ピーク全体の面積が急変しても、実測波形の面積比に合わせて初期振幅を自動補正する機能です。',
          },
        ]}
      />

      {/* Header & Sub-screen Switcher Bar */}
      <section className="panel-card p-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-xs font-mono uppercase tracking-wider text-cyan-400">
            STAGE 03 / BIDIRECTIONAL CONTINUOUS VOIGT FITTING &amp; LIVE STREAM
          </span>
          <h2 className="text-lg sm:text-xl font-bold text-zinc-100 mt-0.5">
            全ファイル連続フィッティング ＆ リアルタイム推移モニター
          </h2>
          {initialExcelPath && (
            <p className="text-sm font-mono text-emerald-400 mt-1">
              初期値ファイル（解析ディレクトリ内）: {initialExcelPath}
            </p>
          )}
          {savedOutputPath && (
            <p className="text-sm font-mono text-cyan-300 mt-0.5">
              解析結果Excel（解析ディレクトリに自動出力済）: {savedOutputPath}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Sub-screen toggle */}
          <div data-tour="step3-subscreen-tabs" className="flex items-center gap-1 p-1 rounded-xl bg-zinc-950 border border-zinc-800">
            <button
              type="button"
              onClick={() => setSubScreen('config')}
              className={`px-3.5 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
                subScreen === 'config'
                  ? 'bg-cyan-500 text-zinc-950 shadow'
                  : 'text-zinc-300 hover:text-zinc-100'
              }`}
            >
              <Sliders className="size-4" />
              <span>① エンジン＆拘束条件設定</span>
            </button>
            <button
              type="button"
              onClick={() => setSubScreen('monitor')}
              className={`px-3.5 py-2 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 ${
                subScreen === 'monitor'
                  ? 'bg-cyan-500 text-zinc-950 shadow'
                  : 'text-zinc-300 hover:text-zinc-100'
              }`}
            >
              <LineChart className="size-4" />
              <span>② リアルタイム波形＆推移モニター</span>
            </button>
          </div>

          <button
            type="button"
            data-tour="step3-start-btn"
            disabled={running}
            onClick={handleStartBatchRun}
            className="btn-primary px-6 py-3"
          >
            {running ? (
              <>
                <RefreshCw className="size-5 animate-spin" aria-hidden="true" />
                <span>全ファイル連続フィッティング実行中...</span>
              </>
            ) : (
              <>
                <Play className="size-5 fill-current" aria-hidden="true" />
                <span>全ファイル連続解析スタート ({batchConfigs.length} グループ)</span>
              </>
            )}
          </button>

          {completedAll && (
            <button
              type="button"
              onClick={onProceedStep4}
              className="btn-emerald px-6 py-3"
            >
              <CheckCircle2 className="size-5" aria-hidden="true" />
              <span>Step 4: 要確認フィット一括検証 ＆ Excel出力へ進む</span>
              <ArrowRight className="size-5" aria-hidden="true" />
            </button>
          )}
        </div>
      </section>

      {error && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-rose-950/60 border border-rose-500/40 text-sm text-rose-200 flex items-center gap-2.5"
        >
          <AlertCircle className="size-5 text-rose-400 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {/* Live Progress Bar */}
      {progressInfo && (
        <section className="panel-card border-cyan-500/40 p-5 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm font-mono tabular-nums">
            <div className="flex items-center gap-2 text-cyan-300 font-bold">
              <Activity className="size-5 text-cyan-400" aria-hidden="true" />
              <span>
                Group [{progressInfo.groupIndex}/{progressInfo.totalGroups}]: {progressInfo.groupId}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-5 text-zinc-300">
              <span>
                File: <strong className="text-zinc-100">#{progressInfo.currentNum}</strong>
              </span>
              <span>
                進捗:{' '}
                <strong className="text-cyan-400">
                  {progressInfo.completedFiles} / {progressInfo.totalFiles} ({fmtFixed(progressInfo.progressPct, 1)}%)
                </strong>
              </span>
              <span>
                相対残差:{' '}
                <strong className="text-emerald-400">{fmtFixed(progressInfo.relativeResidual, 4)}</strong>
              </span>
            </div>
          </div>

          <div className="w-full h-3 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
            <div
              className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 origin-left transition-transform duration-150 ease-out"
              style={{ transform: `scaleX(${Math.min(1, Math.max(0, progressInfo.progressPct / 100))})` }}
            />
          </div>
        </section>
      )}

      {/* SUB-SCREEN 1: Group Engine & Constraint Configuration */}
      {subScreen === 'config' && (
        <section data-tour="step3-group-config" className="panel-card p-6 space-y-5 animate-fade-in">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2.5">
              <Sliders className="size-5 text-amber-400" aria-hidden="true" />
              <div>
                <h3 className="text-base font-bold text-zinc-100">
                  解析対象ピーク・ペア ＆ 詳細パラメータ拘束条件
                </h3>
                <p className="text-sm text-zinc-400">
                  各ピークグループの解析アルゴリズムを選択できます。詳細拘束条件は右端の矢印ボタンから展開できます。
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSubScreen('monitor')}
              className="btn-secondary text-sm"
            >
              <LineChart className="size-4 text-cyan-400" />
              <span>リアルタイム推移モニター画面を表示</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {batchConfigs.map((cfg) => {
              const isExpanded = expandedGroupId === cfg.group_id;
              const isMulti = cfg.peaks.length > 1;
              return (
                <div
                  key={cfg.group_id}
                  className={`rounded-xl border transition-all ${
                    activeGroupId === cfg.group_id
                      ? 'bg-zinc-950 border-cyan-500/60 shadow-md'
                      : 'bg-zinc-950/70 border-zinc-800'
                  }`}
                >
                  <div className="p-4 flex flex-wrap items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => setActiveGroupId(cfg.group_id)}
                      className="text-left flex items-center gap-2.5"
                    >
                      <span className="text-base font-mono font-bold text-zinc-100">
                        {cfg.peaks.join(' + ')}
                      </span>
                      <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-700 text-xs font-mono tabular-nums text-cyan-300">
                        初期値 num=#{cfg.init_num}
                      </span>
                    </button>

                    <div className="flex items-center gap-2">
                      <select
                        aria-label={`${cfg.group_id} 解析エンジン選択`}
                        value={cfg.engine}
                        onChange={(e) =>
                          updateGroupConfig(cfg.group_id, {
                            engine: e.target.value as GroupBatchConfig['engine'],
                          })
                        }
                        className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm font-mono text-zinc-100"
                      >
                        {isMulti ? (
                          <>
                            <option value="2PeaksRatio">2PeaksRatio (強度比R探索)</option>
                            <option value="3PeaksLuders">3PeaksLuders (リュダース3ピーク)</option>
                            <option value="MultiPeaks">MultiPeaks (汎用マルチ)</option>
                          </>
                        ) : (
                          <option value="1Peak">1Peak (単一ピーク連続)</option>
                        )}
                      </select>

                      <button
                        type="button"
                        aria-expanded={isExpanded}
                        aria-label={`${cfg.group_id} 詳細パラメータを展開`}
                        onClick={() =>
                          setExpandedGroupId(isExpanded ? null : cfg.group_id)
                        }
                        className="p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-300"
                      >
                        {isExpanded ? (
                          <ChevronUp className="size-4" aria-hidden="true" />
                        ) : (
                          <ChevronDown className="size-4" aria-hidden="true" />
                        )}
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-zinc-800 p-4 space-y-4 text-sm bg-zinc-900/50">
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs text-zinc-300 mb-1">
                            最小角度 `th_min` (°)
                          </label>
                          <input
                            type="number"
                            step="0.05"
                            value={cfg.th_min ?? 11.0}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, { th_min: Number(e.target.value) })
                            }
                            className="input-field font-mono tabular-nums"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-zinc-300 mb-1">
                            最大角度 `th_max` (°)
                          </label>
                          <input
                            type="number"
                            step="0.05"
                            value={cfg.th_max ?? 12.1}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, { th_max: Number(e.target.value) })
                            }
                            className="input-field font-mono tabular-nums"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-zinc-300 mb-1">
                            残差許容値 `residual_limit`
                          </label>
                          <input
                            type="number"
                            step="0.1"
                            value={cfg.residual_limit}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, {
                                residual_limit: Number(e.target.value),
                              })
                            }
                            className="input-field font-mono tabular-nums"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-zinc-300 mb-1">
                            再試行上限 `max_attempts`
                          </label>
                          <input
                            type="number"
                            step="1"
                            value={cfg.max_attempts}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, {
                                max_attempts: Number(e.target.value),
                              })
                            }
                            className="input-field font-mono tabular-nums"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-zinc-300 mb-1">
                            変態開始 `DIMT_onset_num`
                          </label>
                          <input
                            type="number"
                            step="10"
                            value={cfg.dimt_onset_num}
                            onChange={(e) =>
                              updateGroupConfig(cfg.group_id, {
                                dimt_onset_num: Number(e.target.value),
                              })
                            }
                            className="input-field font-mono tabular-nums"
                          />
                        </div>
                        {isMulti && (
                          <div>
                            <label className="block text-xs text-zinc-300 mb-1">
                              初期強度比 `R` (I2/I1)
                            </label>
                            <input
                              type="number"
                              step="0.02"
                              value={cfg.R}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, { R: Number(e.target.value) })
                              }
                              className="input-field font-mono tabular-nums"
                            />
                          </div>
                        )}
                      </div>

                      {/* Item 6: bcc211-guided physical constraint on bcc110 center & width */}
                      {cfg.peaks.some((pk) => pk === 'bcc110' || pk === 'bcc101') && (
                        <div className="p-3.5 rounded-xl bg-amber-950/35 border border-amber-500/40 space-y-2.5">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <label className="flex items-center gap-2.5 text-sm font-bold text-amber-200 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={cfg.use_bcc211_constraint ?? true}
                                onChange={(e) =>
                                  updateGroupConfig(cfg.group_id, {
                                    use_bcc211_constraint: e.target.checked,
                                  })
                                }
                                className="w-4 h-4 rounded border-amber-500 text-amber-400"
                              />
                              <span>
                                物理拘束オプション: 孤立ピーク `bcc211(112)` から `bcc110(101)` の位置・幅を拘束 (推奨 ON)
                              </span>
                            </label>
                            <span className="px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-xs font-mono text-amber-300">
                              自動で bcc211 を先行解析して参照
                            </span>
                          </div>
                          {(cfg.use_bcc211_constraint ?? true) && (
                            <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-300 pt-1">
                              <span>
                                ブラッグ則 (d110/d211 = √3) による理論中心角 ±Δθ_tol ＆ tanθ 歪みブロードニング則 (×0.70〜1.40)
                              </span>
                              <div className="flex items-center gap-2">
                                <label className="text-amber-200 font-mono">
                                  中心角許容幅 Δθ_tol (°):
                                </label>
                                <input
                                  type="number"
                                  step="0.01"
                                  min="0.005"
                                  max="0.30"
                                  value={cfg.bcc110_center_tol_deg ?? 0.05}
                                  onChange={(e) =>
                                    updateGroupConfig(cfg.group_id, {
                                      bcc110_center_tol_deg: Number(e.target.value),
                                    })
                                  }
                                  className="w-24 bg-zinc-950 border border-amber-500/50 rounded px-2 py-1 font-mono tabular-nums text-zinc-100"
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {cfg.engine === '3PeaksLuders' && (
                        <div className="grid grid-cols-3 gap-3 pt-2 border-t border-zinc-800">
                          <div>
                            <label className="block text-xs text-zinc-300 mb-1">
                              `undeform_initial`
                            </label>
                            <input
                              type="number"
                              value={cfg.undeform_initial}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, {
                                  undeform_initial: Number(e.target.value),
                                })
                              }
                              className="input-field font-mono tabular-nums"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-zinc-300 mb-1">
                              `undeform_end`
                            </label>
                            <input
                              type="number"
                              value={cfg.undeform_end}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, {
                                  undeform_end: Number(e.target.value),
                                })
                              }
                              className="input-field font-mono tabular-nums"
                            />
                          </div>
                          <div>
                            <label className="block text-xs text-zinc-300 mb-1">
                              第3ピーク強度比 `R2`
                            </label>
                            <input
                              type="number"
                              step="0.1"
                              value={cfg.R2}
                              onChange={(e) =>
                                updateGroupConfig(cfg.group_id, { R2: Number(e.target.value) })
                              }
                              className="input-field font-mono tabular-nums"
                            />
                          </div>
                        </div>
                      )}

                      {/* Per-peak `default_fit_limits` editor */}
                      <div className="pt-2 border-t border-zinc-800 space-y-2.5">
                        <div className="text-xs font-bold text-zinc-300">
                          前ステップ追従拘束 (`default_fit_limits`)
                        </div>
                        {cfg.peaks.map((pkName, pkIdx) => {
                          const vKey = `v${pkIdx + 1}`;
                          const lim =
                            cfg.default_fit_limits?.[vKey] || DEFAULT_LIMIT_TEMPLATE;
                          return (
                            <div
                              key={pkName}
                              className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-2"
                            >
                              <div className="text-xs font-mono text-cyan-400 font-bold">
                                {vKey}: {pkName}
                              </div>
                              <div className="grid grid-cols-4 gap-2 text-xs">
                                <div>
                                  <span className="text-zinc-400 block mb-1">center_min</span>
                                  <input
                                    type="number"
                                    step="0.005"
                                    value={lim.center_min_offset}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'center_min_offset',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                                <div>
                                  <span className="text-zinc-400 block mb-1">center_max</span>
                                  <input
                                    type="number"
                                    step="0.005"
                                    value={lim.center_max_offset}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'center_max_offset',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                                <div>
                                  <span className="text-zinc-400 block mb-1">amp_min_fac</span>
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={lim.amplitude_min_factor}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'amplitude_min_factor',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                                <div>
                                  <span className="text-zinc-400 block mb-1">amp_max_fac</span>
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={lim.amplitude_max_factor}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'amplitude_max_factor',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                                <div>
                                  <span className="text-zinc-400 block mb-1">sigma_min_fac</span>
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={lim.sigma_min_factor}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'sigma_min_factor',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                                <div>
                                  <span className="text-zinc-400 block mb-1">sigma_max_fac</span>
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={lim.sigma_max_factor}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'sigma_max_factor',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                                <div>
                                  <span className="text-zinc-400 block mb-1">gamma_min_fac</span>
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={lim.gamma_min_factor}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'gamma_min_factor',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                                <div>
                                  <span className="text-zinc-400 block mb-1">gamma_max_fac</span>
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={lim.gamma_max_factor}
                                    onChange={(e) =>
                                      updatePeakLimit(
                                        cfg.group_id,
                                        pkIdx,
                                        'gamma_max_factor',
                                        Number(e.target.value)
                                      )
                                    }
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-1 font-mono tabular-nums"
                                  />
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* SUB-SCREEN 2: Real-Time Monitor (Waveform & Parameter Trends) */}
      {subScreen === 'monitor' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in">
          {/* Left: Live Currently Processing Waveform Monitor */}
          <section className="lg:col-span-5 panel-card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <span className="text-xs font-mono text-cyan-400">LIVE VOIGT WAVEFORM</span>
                <h3 className="text-base font-bold text-zinc-100">
                  リアルタイム波形フィット＆成分分離モニター
                </h3>
              </div>
              {liveWaveform && (
                <span className="px-3 py-1 rounded-lg bg-cyan-500/15 border border-cyan-500/40 text-sm font-mono tabular-nums text-cyan-300 font-bold">
                  #{liveWaveform.num} ({liveWaveform.filename})
                </span>
              )}
            </div>

            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-2">
              {liveWaveform ? (
                <PlotlyChart
                  data={waveformTraces}
                  layout={{
                    margin: { l: 54, r: 18, t: 22, b: 42 },
                    xaxis: { title: '2θ (deg.)' },
                    yaxis: { title: 'Intensity (a.u.)' },
                  }}
                  className="w-full h-[360px]"
                />
              ) : (
                <div className="h-[360px] flex items-center justify-center text-sm text-zinc-400">
                  「全ファイル連続解析スタート」を押すと処理中波形がライブ描画されます。
                </div>
              )}
            </div>
          </section>

          {/* Right: Live Evolution Scatter Plots (2theta, I, FWHM vs num) */}
          <section className="lg:col-span-7 panel-card p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
              <div>
                <span className="text-xs font-mono text-amber-400">PARAMETER EVOLUTION vs FILE NUM</span>
                <h3 className="text-base font-bold text-zinc-100">
                  回折角 2θ / 面積強度 I / 半値幅 FWHM リアルタイム推移グラフ
                </h3>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {batchConfigs.map((cfg) => (
                  <button
                    key={cfg.group_id}
                    type="button"
                    onClick={() => setActiveGroupId(cfg.group_id)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-mono border transition-all ${
                      activeGroupId === cfg.group_id
                        ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 font-bold'
                        : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    {cfg.peaks.join('+')}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-2">
                <PlotlyChart
                  data={trend2thTraces}
                  layout={{
                    title: { text: '1. 回折角 2θ (deg.) vs ファイル番号 (num)', font: { size: 13, color: '#e4e4e7' } },
                    margin: { l: 62, r: 18, t: 30, b: 36 },
                    xaxis: { title: 'File Number (num)' },
                    yaxis: { title: '2θ (deg.)' },
                  }}
                  className="w-full h-48"
                />
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-2">
                <PlotlyChart
                  data={trendAreaTraces}
                  layout={{
                    title: { text: '2. 積分面積強度 I (a.u.) vs ファイル番号 (num)', font: { size: 13, color: '#e4e4e7' } },
                    margin: { l: 62, r: 18, t: 30, b: 36 },
                    xaxis: { title: 'File Number (num)' },
                    yaxis: { title: 'Area Intensity I' },
                  }}
                  className="w-full h-48"
                />
              </div>

              <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-2">
                <PlotlyChart
                  data={trendFwhmTraces}
                  layout={{
                    title: { text: '3. 合成半値幅 FWHM (deg.) vs ファイル番号 (num)', font: { size: 13, color: '#e4e4e7' } },
                    margin: { l: 62, r: 18, t: 30, b: 36 },
                    xaxis: { title: 'File Number (num)' },
                    yaxis: { title: 'FWHM (deg.)' },
                  }}
                  className="w-full h-48"
                />
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};
