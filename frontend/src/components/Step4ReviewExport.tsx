import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  Layers,
  Play,
  RotateCcw,
  SlidersHorizontal,
} from 'lucide-react';
import {
  BatchGroupResult,
  BatchRefitResponse,
  CandidateFitResult,
} from '../types/xrd';
import { apiGet, apiPost, cn, fmtFixed, fmtSci } from '../lib/utils';
import { PlotlyChart } from './PlotlyChart';
import { Button } from './ui/Button';
import { EmptyCanvas } from './ui/EmptyCanvas';
import { CheckboxRow, FieldLabel, TextInput, UnitNumberInput } from './ui/Field';
import { Notice } from './ui/Notice';
import { Panel, PanelBody, PanelHeader } from './ui/Panel';
import { PlotFrame } from './ui/PlotFrame';
import { SegmentedControl } from './ui/SegmentedControl';
import { StatusBadge } from './ui/StatusBadge';

interface Step4ReviewExportProps {
  folderPath: string;
  specimenName: string;
  batchResults: Record<string, BatchGroupResult>;
  setBatchResults: React.Dispatch<React.SetStateAction<Record<string, BatchGroupResult>>>;
  onProceedStep5: () => void;
}

type SubView = 'outlier_studio' | 'trend_and_export';

interface PeakEditValues {
  center: number;
  wG: number;
  wL: number;
  amplitude: number;
}

interface WaveformInspection {
  num: number;
  filename: string;
  residual_rmse: number;
  relative_residual: number;
  is_outlier: boolean;
  row_data: Record<string, number>;
  waveform: {
    x: number[];
    y_obs: number[];
    y_fit: number[];
    components: Record<string, number[]>;
  };
}

const PEAK_COLORS = ['#38bdf8', '#f59e0b', '#34d399', '#a78bfa', '#f472b6', '#fb7185'];

export const Step4ReviewExport: React.FC<Step4ReviewExportProps> = ({
  folderPath,
  specimenName,
  batchResults,
  setBatchResults,
  onProceedStep5,
}) => {
  const groupList = useMemo(() => Object.values(batchResults), [batchResults]);

  const [activeSubView, setActiveSubView] = useState<SubView>('outlier_studio');
  const [selectedGid, setSelectedGid] = useState<string>(groupList[0]?.group_id ?? '');

  useEffect(() => {
    if (!groupList.length) {
      setSelectedGid('');
      return;
    }
    if (!selectedGid || !batchResults[selectedGid]) {
      setSelectedGid(groupList[0].group_id);
    }
  }, [groupList, selectedGid, batchResults]);

  const activeGroup = selectedGid ? batchResults[selectedGid] : undefined;

  const [selectedNums, setSelectedNums] = useState<number[]>([]);
  const [manualInput, setManualInput] = useState('');
  const [useNeighborInterpolation, setUseNeighborInterpolation] = useState(true);
  const [varyY0, setVaryY0] = useState(true);

  const [inspectNum, setInspectNum] = useState<number | null>(null);
  const [waveform, setWaveform] = useState<WaveformInspection | null>(null);
  const [loadingWaveform, setLoadingWaveform] = useState(false);

  const [rangeMin, setRangeMin] = useState<number>(0);
  const [rangeMax, setRangeMax] = useState<number>(0);
  const [peakParams, setPeakParams] = useState<Record<string, PeakEditValues>>({});

  const [isRefittingSingle, setIsRefittingSingle] = useState(false);
  const [isRefittingBatch, setIsRefittingBatch] = useState(false);
  const [batchSummary, setBatchSummary] = useState<BatchRefitResponse | null>(null);

  const [isExporting, setIsExporting] = useState(false);
  const [exportResult, setExportResult] = useState<{
    saved_path: string;
    used_fallback: boolean;
    sheets: string[];
  } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!activeGroup) return;
    const outliers = activeGroup.outlier_nums || [];
    setSelectedNums([...outliers].sort((a, b) => a - b));
    setBatchSummary(null);
    const defaultNum = outliers[0] ?? activeGroup.rows[0]?.num ?? null;
    setInspectNum(defaultNum);
  }, [selectedGid]);

  const loadWaveform = async (gid: string, num: number) => {
    if (!folderPath || !gid) return;
    setLoadingWaveform(true);
    setErrorMsg(null);
    try {
      const data = await apiGet<WaveformInspection>(
        `/api/fitting/waveform/${encodeURIComponent(gid)}/${num}?folder_path=${encodeURIComponent(folderPath)}`
      );
      setWaveform(data);
      const grp = batchResults[gid];
      if (grp) {
        const xs = data.waveform?.x || [];
        const fallbackMin = xs.length > 0 ? Math.min(...xs) : 0;
        const fallbackMax = xs.length > 0 ? Math.max(...xs) : 0;
        setRangeMin(Number(fmtFixed(grp.th_min ?? fallbackMin, 3)));
        setRangeMax(Number(fmtFixed(grp.th_max ?? fallbackMax, 3)));

        const row = data.row_data || {};
        const nextParams: Record<string, PeakEditValues> = {};
        grp.peaks.forEach((pk) => {
          nextParams[pk] = {
            center: Number(row[`2th_${pk}`] ?? 0),
            wG: Number(row[`wG_${pk}`] ?? 0.05),
            wL: Number(row[`wL_${pk}`] ?? 0.05),
            amplitude: Number(row[`I_${pk}`] ?? 100),
          };
        });
        setPeakParams(nextParams);
      }
    } catch (e: any) {
      setErrorMsg(e.message || '波形読込エラー');
    } finally {
      setLoadingWaveform(false);
    }
  };

  useEffect(() => {
    if (activeGroup && inspectNum !== null && folderPath) {
      loadWaveform(activeGroup.group_id, inspectNum);
    } else {
      setWaveform(null);
    }
  }, [selectedGid, inspectNum]);

  const outlierCountTotal = useMemo(
    () => groupList.reduce((acc, g) => acc + (g.outlier_nums?.length || 0), 0),
    [groupList]
  );

  const outlierSet = useMemo(
    () => new Set(activeGroup?.outlier_nums || []),
    [activeGroup?.outlier_nums]
  );

  const handleToggleQueueNum = (num: number) => {
    setSelectedNums((prev) =>
      prev.includes(num) ? prev.filter((n) => n !== num) : [...prev, num].sort((a, b) => a - b)
    );
  };

  const handleSelectAllOutliers = () => {
    if (!activeGroup) return;
    setSelectedNums([...(activeGroup.outlier_nums || [])].sort((a, b) => a - b));
  };

  const handleSelectPhaseOutliers = (phase: 'gamma' | 'alpha') => {
    if (!activeGroup) return;
    const matchesPhase =
      phase === 'gamma'
        ? activeGroup.peaks.some((p) => p.toLowerCase().includes('gamma') || p.startsWith('fcc'))
        : activeGroup.peaks.some((p) => p.toLowerCase().includes('alpha') || p.startsWith('bcc'));
    if (!matchesPhase) {
      setSelectedNums([]);
      return;
    }
    setSelectedNums([...(activeGroup.outlier_nums || [])].sort((a, b) => a - b));
  };

  const handleClearQueue = () => setSelectedNums([]);

  const handleAddManualNums = () => {
    if (!activeGroup || !manualInput.trim()) return;
    const availableNums = new Set(activeGroup.rows.map((r) => r.num));
    const parsed: number[] = [];
    for (const part of manualInput.split(/[,、\s]+/)) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      if (trimmed.includes('-')) {
        const [aStr, bStr] = trimmed.split('-');
        const a = parseInt(aStr, 10);
        const b = parseInt(bStr, 10);
        if (!Number.isNaN(a) && !Number.isNaN(b)) {
          const start = Math.min(a, b);
          const end = Math.max(a, b);
          for (let n = start; n <= end; n++) {
            if (availableNums.has(n)) parsed.push(n);
          }
        }
      } else {
        const n = parseInt(trimmed, 10);
        if (!Number.isNaN(n) && availableNums.has(n)) parsed.push(n);
      }
    }
    if (parsed.length > 0) {
      setSelectedNums((prev) => Array.from(new Set([...prev, ...parsed])).sort((a, b) => a - b));
      setManualInput('');
    }
  };

  const applyUpdatedRowsToGroup = (
    gid: string,
    updates: Array<{ num: number; updated_row: Record<string, number> }>
  ) => {
    setBatchResults((prev) => {
      const target = prev[gid];
      if (!target) return prev;
      const updateMap = new Map(updates.map((u) => [u.num, u.updated_row]));
      const repairedNums = new Set(updates.map((u) => u.num));
      const nextRows = target.rows.map((row) => {
        const updated = updateMap.get(row.num);
        return updated ? { ...row, ...updated } : row;
      });
      const nextOutlierNums = (target.outlier_nums || []).filter((n) => !repairedNums.has(n));
      return {
        ...prev,
        [gid]: {
          ...target,
          rows: nextRows,
          outlier_nums: nextOutlierNums,
        },
      };
    });
  };

  const handleBatchRefit = async () => {
    if (!activeGroup || selectedNums.length === 0) return;
    setIsRefittingBatch(true);
    setErrorMsg(null);
    setBatchSummary(null);
    try {
      const items = selectedNums.map((num) => ({
        group_id: activeGroup.group_id,
        num,
        peaks: activeGroup.peaks,
        range_min: rangeMin || undefined,
        range_max: rangeMax || undefined,
        vary_y0: varyY0,
      }));
      const res = await apiPost<BatchRefitResponse>('/api/fitting/refit-batch', {
        folder_path: folderPath,
        use_neighbor_interpolation: useNeighborInterpolation,
        vary_y0: varyY0,
        items,
      });
      setBatchSummary(res);
      const validUpdates = (res.repaired_items || []).map((item) => ({
        num: item.num,
        updated_row: item.updated_row,
      }));
      if (validUpdates.length > 0) {
        applyUpdatedRowsToGroup(activeGroup.group_id, validUpdates);
      }
      if (inspectNum !== null) {
        await loadWaveform(activeGroup.group_id, inspectNum);
      }
    } catch (e: any) {
      setErrorMsg(e.message || '一括再Fitエラー');
    } finally {
      setIsRefittingBatch(false);
    }
  };

  const buildOrderedInitialArrays = () => {
    if (!activeGroup) return null;
    const initial_centers = activeGroup.peaks.map((pk) => peakParams[pk]?.center ?? 0);
    const initial_wG = activeGroup.peaks.map((pk) => peakParams[pk]?.wG ?? 0.05);
    const initial_wL = activeGroup.peaks.map((pk) => peakParams[pk]?.wL ?? 0.05);
    const initial_A = activeGroup.peaks.map((pk) => peakParams[pk]?.amplitude ?? 100);
    return { initial_centers, initial_wG, initial_wL, initial_A };
  };

  const handleSingleRefit = async (advanceAfter = false) => {
    if (!activeGroup || inspectNum === null) return;
    const arrays = buildOrderedInitialArrays();
    if (!arrays) return;
    setIsRefittingSingle(true);
    setErrorMsg(null);
    try {
      const res = await apiPost<{
        status: string;
        num: number;
        updated_row: Record<string, number>;
        fit: CandidateFitResult;
      }>('/api/fitting/refit-file', {
        folder_path: folderPath,
        group_id: activeGroup.group_id,
        num: inspectNum,
        peaks: activeGroup.peaks,
        range_min: rangeMin,
        range_max: rangeMax,
        ...arrays,
        vary_y0: varyY0,
      });

      applyUpdatedRowsToGroup(activeGroup.group_id, [
        { num: res.num, updated_row: res.updated_row },
      ]);
      await loadWaveform(activeGroup.group_id, inspectNum);

      if (advanceAfter) {
        const remaining = (activeGroup.outlier_nums || []).filter((n) => n !== inspectNum);
        const nextOutlier = remaining.find((n) => n > inspectNum) ?? remaining[0];
        if (nextOutlier !== undefined) {
          setInspectNum(nextOutlier);
        }
      }
    } catch (e: any) {
      setErrorMsg(e.message || '再Fitエラー');
    } finally {
      setIsRefittingSingle(false);
    }
  };

  const handleStepQueue = (dir: -1 | 1) => {
    if (!activeGroup || inspectNum === null) return;
    const pool = selectedNums.length > 0 ? selectedNums : activeGroup.rows.map((r) => r.num);
    if (!pool.length) return;
    const idx = pool.indexOf(inspectNum);
    const nextIdx = idx === -1 ? 0 : (idx + dir + pool.length) % pool.length;
    setInspectNum(pool[nextIdx]);
  };

  const handleApplyParamsToSelected = async () => {
    if (!activeGroup || selectedNums.length === 0) return;
    const arrays = buildOrderedInitialArrays();
    if (!arrays) return;
    setIsRefittingBatch(true);
    setErrorMsg(null);
    setBatchSummary(null);
    try {
      const items = selectedNums.map((num) => ({
        group_id: activeGroup.group_id,
        num,
        peaks: activeGroup.peaks,
        range_min: rangeMin || undefined,
        range_max: rangeMax || undefined,
        ...arrays,
        vary_y0: varyY0,
      }));
      const res = await apiPost<BatchRefitResponse>('/api/fitting/refit-batch', {
        folder_path: folderPath,
        use_neighbor_interpolation: false,
        vary_y0: varyY0,
        items,
      });
      setBatchSummary(res);
      const validUpdates = (res.repaired_items || []).map((item) => ({
        num: item.num,
        updated_row: item.updated_row,
      }));
      if (validUpdates.length > 0) {
        applyUpdatedRowsToGroup(activeGroup.group_id, validUpdates);
      }
      if (inspectNum !== null) {
        await loadWaveform(activeGroup.group_id, inspectNum);
      }
    } catch (e: any) {
      setErrorMsg(e.message || '一括適用エラー');
    } finally {
      setIsRefittingBatch(false);
    }
  };

  const handleExportExcel = async () => {
    if (groupList.length === 0) return;
    setIsExporting(true);
    setErrorMsg(null);
    try {
      const res = await apiPost<{
        status: string;
        saved_path: string;
        used_fallback: boolean;
        sheets: string[];
      }>('/api/fitting/export', {
        folder_path: folderPath,
        specimen_name: specimenName || undefined,
        groups: groupList.map((grp) => ({
          sheet_name: grp.sheet_name,
          peaks: grp.peaks,
          rows: grp.rows,
          best_R: grp.best_R,
          history_R: grp.history_R,
          history_residual: grp.history_residual,
        })),
      });
      setExportResult(res);
    } catch (e: any) {
      setErrorMsg(e.message || 'Excel出力エラー');
    } finally {
      setIsExporting(false);
    }
  };

  const waveformTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!waveform?.waveform) return [];
    const { x, y_obs, y_fit, components } = waveform.waveform;
    const traces: Record<string, unknown>[] = [
      {
        x,
        y: y_obs,
        type: 'scatter',
        mode: 'lines',
        name: '実測',
        line: { color: '#787f90', width: 1.4 },
      },
      {
        x,
        y: y_fit,
        type: 'scatter',
        mode: 'lines',
        name: '合成 Fit',
        line: { color: '#34d399', width: 2 },
      },
    ];
    Object.entries(components || {}).forEach(([pk, yComp], idx) => {
      traces.push({
        x,
        y: yComp,
        type: 'scatter',
        mode: 'lines',
        name: pk,
        line: {
          color: PEAK_COLORS[idx % PEAK_COLORS.length],
          width: 1.5,
          dash: 'dot',
        },
      });
    });
    return traces;
  }, [waveform]);

  const trendCenterTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!activeGroup) return [];
    const xs = activeGroup.rows.map((r) => r.num);
    return activeGroup.peaks.map((pk, idx) => ({
      x: xs,
      y: activeGroup.rows.map((r) => r[`2th_${pk}`] ?? null),
      type: 'scatter',
      mode: 'lines+markers',
      name: `2θ (${pk})`,
      marker: { size: 4, color: PEAK_COLORS[idx % PEAK_COLORS.length] },
      line: { width: 1.5, color: PEAK_COLORS[idx % PEAK_COLORS.length] },
    }));
  }, [activeGroup]);

  const trendIntensityTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!activeGroup) return [];
    const xs = activeGroup.rows.map((r) => r.num);
    return activeGroup.peaks.map((pk, idx) => ({
      x: xs,
      y: activeGroup.rows.map((r) => r[`I_${pk}`] ?? null),
      type: 'scatter',
      mode: 'lines+markers',
      name: `I (${pk})`,
      marker: { size: 4, color: PEAK_COLORS[idx % PEAK_COLORS.length] },
      line: { width: 1.5, color: PEAK_COLORS[idx % PEAK_COLORS.length] },
    }));
  }, [activeGroup]);

  const trendResidualTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!activeGroup) return [];
    const xs = activeGroup.rows.map((r) => r.num);
    const colors = activeGroup.rows.map((r) =>
      outlierSet.has(r.num) ? '#fb7185' : '#38bdf8'
    );
    return [
      {
        x: xs,
        y: activeGroup.rows.map((r) => r.residual ?? 0),
        type: 'scatter',
        mode: 'lines+markers',
        name: '相対残差',
        line: { width: 1.25, color: '#525866' },
        marker: { size: 5, color: colors },
      },
    ];
  }, [activeGroup, outlierSet]);

  if (groupList.length === 0) {
    return <EmptyCanvas className="h-72" label="解析結果なし" meta="Step 3" />;
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <Panel>
        <div className="px-3.5 py-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <SegmentedControl<SubView>
              ariaLabel="表示切替"
              size="sm"
              value={activeSubView}
              onChange={setActiveSubView}
              options={[
                {
                  value: 'outlier_studio',
                  label: '波形検証',
                  badge: outlierCountTotal > 0 ? outlierCountTotal : undefined,
                  accent: outlierCountTotal > 0 ? 'amber' : 'sky',
                },
                {
                  value: 'trend_and_export',
                  label: 'トレンド・出力',
                  accent: 'emerald',
                },
              ]}
            />

            {groupList.length > 1 && (
              <div className="flex items-center gap-1 border-l border-[#22262f] pl-2">
                {groupList.map((g) => {
                  const count = g.outlier_nums?.length || 0;
                  return (
                    <button
                      key={g.group_id}
                      type="button"
                      onClick={() => setSelectedGid(g.group_id)}
                      className={cn(
                        'h-6 px-2 rounded text-[11px] font-medium flex items-center gap-1.5 border transition-colors whitespace-nowrap',
                        g.group_id === selectedGid
                          ? 'bg-[#1c2028] text-[#eef0f4] border-sky-500/40'
                          : 'bg-transparent text-[#858d9c] border-transparent hover:text-[#eef0f4] hover:bg-[#15181e]'
                      )}
                    >
                      <span className="truncate max-w-[140px]">{g.sheet_name}</span>
                      {count > 0 && (
                        <span className="text-[10px] font-mono tabular-nums text-amber-300">
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge tone={outlierCountTotal > 0 ? 'amber' : 'emerald'} dot mono>
              外れ値 {outlierCountTotal}
            </StatusBadge>
            <Button
              variant="emerald"
              size="sm"
              onClick={onProceedStep5}
              disabled={groupList.length === 0}
            >
              <span>次へ: 物理量</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </Panel>

      {errorMsg && <Notice tone="error">{errorMsg}</Notice>}

      {batchSummary && (
        <Notice tone="success">
          再Fit完了: {batchSummary.repaired_count}件更新
          {batchSummary.saved_path ? ` (${batchSummary.saved_path})` : ''}
        </Notice>
      )}

      {activeSubView === 'outlier_studio' && activeGroup && (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-3">
          {/* Left 3 cols */}
          <div className="xl:col-span-3 space-y-3">
            <Panel>
              <PanelHeader
                title="キュー"
                subtitle={`${selectedNums.length}/${activeGroup.rows.length}`}
              />
              <PanelBody className="space-y-2.5">
                <div className="grid grid-cols-2 gap-1.5">
                  <Button variant="secondary" size="xs" onClick={handleSelectAllOutliers}>
                    全外れ値
                  </Button>
                  <Button variant="ghost" size="xs" onClick={handleClearQueue}>
                    解除
                  </Button>
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleSelectPhaseOutliers('gamma')}
                  >
                    γ相
                  </Button>
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleSelectPhaseOutliers('alpha')}
                  >
                    α&apos;相
                  </Button>
                </div>

                <div className="flex items-center gap-1.5">
                  <TextInput
                    mono
                    value={manualInput}
                    onChange={(e) => setManualInput(e.target.value)}
                    placeholder="12, 15-18"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleAddManualNums();
                    }}
                  />
                  <Button variant="secondary" size="sm" onClick={handleAddManualNums}>
                    追加
                  </Button>
                </div>

                <CheckboxRow
                  checked={useNeighborInterpolation}
                  onChange={setUseNeighborInterpolation}
                  label="近傍フレーム補間"
                />

                <Button
                  variant="amber"
                  size="sm"
                  block
                  onClick={handleBatchRefit}
                  disabled={isRefittingBatch || selectedNums.length === 0}
                >
                  <Play className="w-3 h-3 fill-current" />
                  <span>
                    {isRefittingBatch ? '実行中...' : `一括再Fit (${selectedNums.length})`}
                  </span>
                </Button>
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader title="フレーム" subtitle={`${activeGroup.rows.length}`} />
              <div className="max-h-[420px] overflow-y-auto divide-y divide-[#1a1d25]">
                {activeGroup.rows.map((row) => {
                  const isInspected = row.num === inspectNum;
                  const isQueued = selectedNums.includes(row.num);
                  const isOutlier = outlierSet.has(row.num);
                  return (
                    <div
                      key={row.num}
                      className={cn(
                        'flex items-center gap-2 px-3 py-1.5 text-[11px] transition-colors',
                        isInspected
                          ? 'bg-[#1c2028] text-[#eef0f4]'
                          : 'hover:bg-[#15181e] text-[#98a0ae]'
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={isQueued}
                        onChange={() => handleToggleQueueNum(row.num)}
                        aria-label={`#${row.num}`}
                        className="w-3.5 h-3.5 rounded border-[#303644] bg-[#08090c] accent-sky-500 shrink-0"
                      />
                      <button
                        type="button"
                        onClick={() => setInspectNum(row.num)}
                        className="flex-1 flex items-center justify-between gap-2 text-left min-w-0"
                      >
                        <span className="font-mono tabular-nums font-medium">#{row.num}</span>
                        <span className="font-mono tabular-nums text-[10px] text-[#5d6473] truncate">
                          R={fmtFixed(row.residual, 4)}
                        </span>
                        {isOutlier ? (
                          <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                        ) : (
                          <Check className="w-3 h-3 text-emerald-400/70 shrink-0" />
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            </Panel>
          </div>

          {/* Center 6 cols */}
          <div className="xl:col-span-6">
            <PlotFrame
              title={waveform ? `#${waveform.num} (${waveform.filename})` : '波形インスペクター'}
              subtitle={
                waveform
                  ? `R=${(waveform.relative_residual * 100).toFixed(2)}% · RMSE ${fmtFixed(waveform.residual_rmse, 2)}`
                  : undefined
              }
              toolbar={
                <div className="flex items-center gap-1.5">
                  {waveform?.is_outlier && (
                    <StatusBadge tone="amber" dot>
                      外れ値
                    </StatusBadge>
                  )}
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleStepQueue(-1)}
                    title="前"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleStepQueue(1)}
                    title="次"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              }
              subbar={
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-[#5d6473]">
                  <span>{activeGroup.sheet_name}</span>
                  <span className="tabular-nums">
                    best_R {activeGroup.best_R !== undefined ? fmtFixed(activeGroup.best_R, 4) : '—'}
                  </span>
                </div>
              }
            >
              {loadingWaveform ? (
                <div className="h-[460px] flex items-center justify-center text-[11px] font-mono text-[#5d6473]">
                  Loading...
                </div>
              ) : waveformTraces.length > 0 ? (
                <PlotlyChart
                  data={waveformTraces}
                  layout={{
                    xaxis: { title: '2θ [deg]' },
                    yaxis: { title: 'Intensity' },
                    margin: { t: 14, r: 16, b: 40, l: 54 },
                  }}
                  className="w-full h-[460px]"
                />
              ) : (
                <EmptyCanvas className="h-[460px]" label="フレーム未選択" />
              )}
            </PlotFrame>
          </div>

          {/* Right 3 cols */}
          <div className="xl:col-span-3 space-y-3">
            <Panel>
              <PanelHeader
                title="パラメータ"
                subtitle={inspectNum !== null ? `#${inspectNum}` : undefined}
                actions={<SlidersHorizontal className="w-3.5 h-3.5 text-[#5d6473]" />}
              />
              <PanelBody className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <FieldLabel>min (2θ)</FieldLabel>
                    <UnitNumberInput
                      unit="°"
                      step="0.02"
                      value={rangeMin}
                      onChange={(e) => setRangeMin(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div>
                    <FieldLabel>max (2θ)</FieldLabel>
                    <UnitNumberInput
                      unit="°"
                      step="0.02"
                      value={rangeMax}
                      onChange={(e) => setRangeMax(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                </div>

                <CheckboxRow checked={varyY0} onChange={setVaryY0} label="y0 可変" />

                <div className="space-y-2 max-h-[340px] overflow-y-auto pr-0.5">
                  {activeGroup.peaks.map((pk, idx) => {
                    const p = peakParams[pk] || {
                      center: 0,
                      wG: 0.05,
                      wL: 0.05,
                      amplitude: 100,
                    };
                    const updatePeak = (field: keyof PeakEditValues, val: number) => {
                      setPeakParams((prev) => ({
                        ...prev,
                        [pk]: {
                          ...p,
                          [field]: val,
                        },
                      }));
                    };
                    return (
                      <div
                        key={pk}
                        className="bg-[#08090c] border border-[#22262f] rounded p-2 space-y-1.5"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: PEAK_COLORS[idx % PEAK_COLORS.length] }}
                          />
                          <span className="text-[11px] font-mono font-semibold text-[#eef0f4] truncate">
                            {pk}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5">
                          <div>
                            <FieldLabel>2θ</FieldLabel>
                            <UnitNumberInput
                              unit="°"
                              step="0.01"
                              value={p.center}
                              onChange={(e) =>
                                updatePeak('center', parseFloat(e.target.value) || 0)
                              }
                            />
                          </div>
                          <div>
                            <FieldLabel>I</FieldLabel>
                            <UnitNumberInput
                              step="10"
                              value={p.amplitude}
                              onChange={(e) =>
                                updatePeak('amplitude', parseFloat(e.target.value) || 0)
                              }
                            />
                          </div>
                          <div>
                            <FieldLabel>wG</FieldLabel>
                            <UnitNumberInput
                              step="0.005"
                              value={p.wG}
                              onChange={(e) =>
                                updatePeak('wG', parseFloat(e.target.value) || 0)
                              }
                            />
                          </div>
                          <div>
                            <FieldLabel>wL</FieldLabel>
                            <UnitNumberInput
                              step="0.005"
                              value={p.wL}
                              onChange={(e) =>
                                updatePeak('wL', parseFloat(e.target.value) || 0)
                              }
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="space-y-1.5 pt-2 border-t border-[#22262f]">
                  <Button
                    variant="primary"
                    size="sm"
                    block
                    onClick={() => handleSingleRefit(false)}
                    disabled={isRefittingSingle || inspectNum === null}
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>{isRefittingSingle ? '実行中...' : '再Fit'}</span>
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    block
                    onClick={() => handleSingleRefit(true)}
                    disabled={isRefittingSingle || inspectNum === null}
                  >
                    <span>再Fit → 次へ</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="xs"
                    block
                    onClick={handleApplyParamsToSelected}
                    disabled={isRefittingBatch || selectedNums.length === 0}
                  >
                    <Layers className="w-3 h-3" />
                    <span>選択 {selectedNums.length}件へ適用</span>
                  </Button>
                </div>
              </PanelBody>
            </Panel>
          </div>
        </div>
      )}

      {activeSubView === 'trend_and_export' && activeGroup && (
        <div className="space-y-3">
          <Panel>
            <PanelHeader
              title="Excel 出力"
              subtitle={`${groupList.length} sheets`}
              actions={
                <Button
                  variant="emerald"
                  size="sm"
                  onClick={handleExportExcel}
                  disabled={isExporting}
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{isExporting ? '出力中...' : 'エクスポート'}</span>
                </Button>
              }
            />
            {exportResult && (
              <PanelBody>
                <Notice tone={exportResult.used_fallback ? 'warning' : 'success'}>
                  <div className="font-mono text-[11px]">{exportResult.saved_path}</div>
                </Notice>
              </PanelBody>
            )}
          </Panel>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <PlotFrame title="ピーク位置 (2θ)" subtitle="クリックで波形へ">
              <PlotlyChart
                data={trendCenterTraces}
                layout={{
                  xaxis: { title: '#' },
                  yaxis: { title: '2θ [deg]' },
                  margin: { t: 14, r: 16, b: 38, l: 54 },
                }}
                className="w-full h-[300px]"
                onPointClick={(pt) => {
                  if (typeof pt.x === 'number') {
                    setInspectNum(pt.x);
                    setActiveSubView('outlier_studio');
                  }
                }}
              />
            </PlotFrame>

            <PlotFrame title="積分強度 (I)" subtitle="クリックで波形へ">
              <PlotlyChart
                data={trendIntensityTraces}
                layout={{
                  xaxis: { title: '#' },
                  yaxis: { title: 'Intensity' },
                  margin: { t: 14, r: 16, b: 38, l: 54 },
                }}
                className="w-full h-[300px]"
                onPointClick={(pt) => {
                  if (typeof pt.x === 'number') {
                    setInspectNum(pt.x);
                    setActiveSubView('outlier_studio');
                  }
                }}
              />
            </PlotFrame>
          </div>

          <PlotFrame title="相対残差" subtitle="赤: 外れ値 · クリックで波形へ">
            <PlotlyChart
              data={trendResidualTraces}
              layout={{
                xaxis: { title: '#' },
                yaxis: { title: 'Relative Residual' },
                margin: { t: 14, r: 16, b: 38, l: 54 },
              }}
              className="w-full h-[240px]"
              onPointClick={(pt) => {
                if (typeof pt.x === 'number') {
                  setInspectNum(pt.x);
                  setActiveSubView('outlier_studio');
                }
              }}
            />
          </PlotFrame>

          <Panel>
            <PanelHeader
              title="パラメータ一覧"
              subtitle={`${activeGroup.sheet_name} · ${activeGroup.rows.length}`}
            />
            <div className="max-h-[320px] overflow-auto">
              <table className="w-full text-[11px] font-mono tabular-nums border-collapse">
                <thead className="sticky top-0 bg-[#101216] border-b border-[#22262f] text-[#858d9c]">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">#</th>
                    <th className="text-left px-3 py-2 font-medium">状態</th>
                    <th className="text-right px-3 py-2 font-medium">残差</th>
                    {activeGroup.peaks.map((pk) => (
                      <React.Fragment key={pk}>
                        <th className="text-right px-3 py-2 font-medium">2θ ({pk})</th>
                        <th className="text-right px-3 py-2 font-medium">I ({pk})</th>
                        <th className="text-right px-3 py-2 font-medium">FWHM ({pk})</th>
                      </React.Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1d25]">
                  {activeGroup.rows.map((row) => {
                    const isOutlier = outlierSet.has(row.num);
                    return (
                      <tr
                        key={row.num}
                        onClick={() => {
                          setInspectNum(row.num);
                          setActiveSubView('outlier_studio');
                        }}
                        className="hover:bg-[#1c2028] cursor-pointer text-[#98a0ae]"
                      >
                        <td className="px-3 py-1.5 text-[#eef0f4]">{row.num}</td>
                        <td className="px-3 py-1.5">
                          {isOutlier ? (
                            <span className="text-amber-400">外れ値</span>
                          ) : (
                            <span className="text-emerald-400">正常</span>
                          )}
                        </td>
                        <td className="px-3 py-1.5 text-right">{fmtSci(row.residual, 2)}</td>
                        {activeGroup.peaks.map((pk) => (
                          <React.Fragment key={pk}>
                            <td className="px-3 py-1.5 text-right">
                              {fmtFixed(row[`2th_${pk}`], 4)}
                            </td>
                            <td className="px-3 py-1.5 text-right">
                              {fmtFixed(row[`I_${pk}`], 1)}
                            </td>
                            <td className="px-3 py-1.5 text-right">
                              {fmtFixed(row[`FWHM_${pk}`], 4)}
                            </td>
                          </React.Fragment>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
};
