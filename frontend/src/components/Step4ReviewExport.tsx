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
      setErrorMsg(e.message || '波形の読み込みに失敗しました');
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
        ? activeGroup.peaks.some((p) => p.toLowerCase().includes('gamma'))
        : activeGroup.peaks.some((p) => p.toLowerCase().includes('alpha'));
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
      setErrorMsg(e.message || '一括再Fitに失敗しました');
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
      setErrorMsg(e.message || '単体再Fitに失敗しました');
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
      setErrorMsg(e.message || '選択キューへの適用に失敗しました');
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
      setErrorMsg(e.message || 'Excel出力に失敗しました');
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
        name: '実測値',
        line: { color: '#787f90', width: 1.4 },
      },
      {
        x,
        y: y_fit,
        type: 'scatter',
        mode: 'lines',
        name: '合成フィッティング',
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
    return (
      <Panel className="max-w-xl mx-auto mt-8">
        <PanelHeader title="バッチフィッティング結果がありません" />
        <PanelBody>
          <p className="text-[12px] text-[#787f90]">
            Step 3 でバッチフィッティングを実行すると、外れ値の検証・手動再フィッティング・Excel 出力が可能になります。
          </p>
        </PanelBody>
      </Panel>
    );
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#121418] border border-[#23262e] rounded-md px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl<SubView>
            ariaLabel="検証ビュー切替"
            value={activeSubView}
            onChange={setActiveSubView}
            options={[
              {
                value: 'outlier_studio',
                label: '波形・外れ値修正',
                badge: outlierCountTotal > 0 ? outlierCountTotal : undefined,
                accent: outlierCountTotal > 0 ? 'amber' : 'sky',
              },
              {
                value: 'trend_and_export',
                label: '時系列トレンド・Excel出力',
                accent: 'emerald',
              },
            ]}
          />

          {groupList.length > 1 && (
            <div className="flex items-center gap-1 border-l border-[#23262e] pl-2">
              {groupList.map((g) => {
                const count = g.outlier_nums?.length || 0;
                return (
                  <button
                    key={g.group_id}
                    type="button"
                    onClick={() => setSelectedGid(g.group_id)}
                    className={cn(
                      'h-7 px-2.5 rounded text-[11px] font-medium flex items-center gap-1.5 border transition-colors whitespace-nowrap',
                      g.group_id === selectedGid
                        ? 'bg-[#1c1f26] text-[#eceef2] border-[#38bdf8]/40'
                        : 'bg-transparent text-[#787f90] border-transparent hover:text-[#b4b9c4] hover:bg-[#16181d]'
                    )}
                  >
                    <span className="truncate max-w-[140px]">{g.sheet_name}</span>
                    {count > 0 && (
                      <span className="text-[10px] font-mono tabular-nums text-[#f59e0b]">
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
          <StatusBadge
            tone={outlierCountTotal > 0 ? 'amber' : 'emerald'}
            dot
            mono
          >
            外れ値 {outlierCountTotal}件
          </StatusBadge>
          <Button
            variant="emerald"
            size="sm"
            onClick={onProceedStep5}
            disabled={groupList.length === 0}
          >
            <span>物性値・転位密度解析へ</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {errorMsg && <Notice tone="error">{errorMsg}</Notice>}

      {batchSummary && (
        <Notice tone="success">
          一括再フィッティング完了: {batchSummary.repaired_count}件を更新しました
          {batchSummary.saved_path ? ` (${batchSummary.saved_path})` : ''}
        </Notice>
      )}

      {activeSubView === 'outlier_studio' && activeGroup && (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-3">
          {/* Left 3 cols: Queue & file list */}
          <div className="xl:col-span-3 space-y-3">
            <Panel>
              <PanelHeader
                title="再フィッティングキュー"
                subtitle={`${selectedNums.length} / ${activeGroup.rows.length} 選択`}
              />
              <PanelBody className="space-y-2.5">
                <div className="grid grid-cols-2 gap-1.5">
                  <Button variant="secondary" size="xs" onClick={handleSelectAllOutliers}>
                    全外れ値
                  </Button>
                  <Button variant="ghost" size="xs" onClick={handleClearQueue}>
                    選択解除
                  </Button>
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleSelectPhaseOutliers('gamma')}
                  >
                    γ相のみ
                  </Button>
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleSelectPhaseOutliers('alpha')}
                  >
                    α'相のみ
                  </Button>
                </div>

                <div className="flex items-center gap-1.5">
                  <TextInput
                    mono
                    value={manualInput}
                    onChange={(e) => setManualInput(e.target.value)}
                    placeholder="番号追加 (例: 12, 15-18)"
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
                  label="隣接正常フレームから初期値を自動補間"
                />

                <Button
                  variant="amber"
                  size="sm"
                  block
                  onClick={handleBatchRefit}
                  disabled={isRefittingBatch || selectedNums.length === 0}
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>
                    {isRefittingBatch
                      ? '一括再Fit中...'
                      : `選択 ${selectedNums.length}件を一括再Fit`}
                  </span>
                </Button>
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader
                title="ファイル一覧"
                subtitle={`${activeGroup.rows.length}件`}
              />
              <div className="max-h-[420px] overflow-y-auto divide-y divide-[#1a1d24]">
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
                          ? 'bg-[#1c1f26] text-[#eceef2]'
                          : 'hover:bg-[#16181d] text-[#b4b9c4]'
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={isQueued}
                        onChange={() => handleToggleQueueNum(row.num)}
                        aria-label={`#${row.num} を選択`}
                        className="w-3.5 h-3.5 rounded border-[#2e323d] bg-[#0a0b0e] accent-[#38bdf8] shrink-0"
                      />
                      <button
                        type="button"
                        onClick={() => setInspectNum(row.num)}
                        className="flex-1 flex items-center justify-between gap-2 text-left min-w-0"
                      >
                        <span className="font-mono tabular-nums font-medium">
                          #{row.num}
                        </span>
                        <span className="font-mono tabular-nums text-[10px] text-[#787f90] truncate">
                          R={fmtFixed(row.residual, 4)}
                        </span>
                        {isOutlier ? (
                          <span className="inline-flex items-center gap-1 text-[10px] text-[#f59e0b] shrink-0">
                            <AlertTriangle className="w-3 h-3" />
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] text-[#34d399]/70 shrink-0">
                            <Check className="w-3 h-3" />
                          </span>
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            </Panel>
          </div>

          {/* Center 6 cols: Waveform Plot */}
          <div className="xl:col-span-6">
            <PlotFrame
              title={
                waveform
                  ? `#${waveform.num} (${waveform.filename})`
                  : '波形インスペクター'
              }
              subtitle={
                waveform
                  ? `相対残差 ${(waveform.relative_residual * 100).toFixed(2)}% / RMSE ${fmtFixed(waveform.residual_rmse, 2)}`
                  : 'ファイルを選択'
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
                    title="前のファイル"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="secondary"
                    size="xs"
                    onClick={() => handleStepQueue(1)}
                    title="次のファイル"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              }
              subbar={
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#787f90]">
                  <span>グループ: {activeGroup.sheet_name}</span>
                  <span className="font-mono tabular-nums">
                    best_R = {activeGroup.best_R !== undefined ? fmtFixed(activeGroup.best_R, 4) : '—'}
                  </span>
                </div>
              }
            >
              {loadingWaveform ? (
                <div className="h-[460px] flex items-center justify-center text-[12px] text-[#787f90]">
                  波形データを読み込み中...
                </div>
              ) : waveformTraces.length > 0 ? (
                <PlotlyChart
                  data={waveformTraces}
                  layout={{
                    xaxis: { title: '2θ [deg]' },
                    yaxis: { title: '強度 [counts]' },
                    margin: { t: 16, r: 16, b: 44, l: 56 },
                  }}
                  className="w-full h-[460px]"
                />
              ) : (
                <div className="h-[460px] flex items-center justify-center text-[12px] text-[#787f90]">
                  左のリストから番号を選択してください
                </div>
              )}
            </PlotFrame>
          </div>

          {/* Right 3 cols: Parameter Inspector & Single Refit */}
          <div className="xl:col-span-3 space-y-3">
            <Panel>
              <PanelHeader
                title="初期パラメータ編集"
                subtitle={inspectNum !== null ? `#${inspectNum}` : undefined}
                actions={
                  <SlidersHorizontal className="w-3.5 h-3.5 text-[#787f90]" />
                }
              />
              <PanelBody className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <FieldLabel>Fit下限 (2θ)</FieldLabel>
                    <UnitNumberInput
                      unit="°"
                      step="0.02"
                      value={rangeMin}
                      onChange={(e) => setRangeMin(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div>
                    <FieldLabel>Fit上限 (2θ)</FieldLabel>
                    <UnitNumberInput
                      unit="°"
                      step="0.02"
                      value={rangeMax}
                      onChange={(e) => setRangeMax(parseFloat(e.target.value) || 0)}
                    />
                  </div>
                </div>

                <CheckboxRow
                  checked={varyY0}
                  onChange={setVaryY0}
                  label="ベースライン y0 を可変にする"
                />

                <div className="space-y-2.5 max-h-[340px] overflow-y-auto pr-0.5">
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
                        className="bg-[#0a0b0e] border border-[#23262e] rounded p-2.5 space-y-2"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ backgroundColor: PEAK_COLORS[idx % PEAK_COLORS.length] }}
                          />
                          <span className="text-[11px] font-medium text-[#eceef2] truncate">
                            {pk}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5">
                          <div>
                            <FieldLabel>中心 2θ</FieldLabel>
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
                            <FieldLabel>積分強度 I</FieldLabel>
                            <UnitNumberInput
                              step="10"
                              value={p.amplitude}
                              onChange={(e) =>
                                updatePeak('amplitude', parseFloat(e.target.value) || 0)
                              }
                            />
                          </div>
                          <div>
                            <FieldLabel>Gauss幅 wG</FieldLabel>
                            <UnitNumberInput
                              step="0.005"
                              value={p.wG}
                              onChange={(e) =>
                                updatePeak('wG', parseFloat(e.target.value) || 0)
                              }
                            />
                          </div>
                          <div>
                            <FieldLabel>Lorentz幅 wL</FieldLabel>
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

                <div className="space-y-1.5 pt-1 border-t border-[#23262e]">
                  <Button
                    variant="primary"
                    size="sm"
                    block
                    onClick={() => handleSingleRefit(false)}
                    disabled={isRefittingSingle || inspectNum === null}
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>{isRefittingSingle ? '再Fit実行中...' : '現在フレームを再Fit'}</span>
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    block
                    onClick={() => handleSingleRefit(true)}
                    disabled={isRefittingSingle || inspectNum === null}
                  >
                    <span>再Fitして次の外れ値へ</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="xs"
                    block
                    onClick={handleApplyParamsToSelected}
                    disabled={isRefittingBatch || selectedNums.length === 0}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>この初期値を選択 {selectedNums.length}件に一括適用</span>
                  </Button>
                </div>
              </PanelBody>
            </Panel>
          </div>
        </div>
      )}

      {activeSubView === 'trend_and_export' && activeGroup && (
        <div className="space-y-3">
          {/* Export bar */}
          <Panel>
            <PanelHeader
              title="Excel ワークブック出力"
              subtitle={`グループ数: ${groupList.length}`}
              actions={
                <Button
                  variant="emerald"
                  size="sm"
                  onClick={handleExportExcel}
                  disabled={isExporting}
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{isExporting ? '出力中...' : 'Excel (.xlsx) を出力'}</span>
                </Button>
              }
            />
            {exportResult && (
              <PanelBody>
                <Notice tone={exportResult.used_fallback ? 'warning' : 'success'}>
                  <div className="space-y-1">
                    <div className="font-medium">
                      保存完了: <span className="font-mono">{exportResult.saved_path}</span>
                    </div>
                    <div className="text-[11px] opacity-90">
                      シート: {exportResult.sheets.join(', ')}
                      {exportResult.used_fallback
                        ? ' (元ファイルが使用中だったため別名で保存しました)'
                        : ''}
                    </div>
                  </div>
                </Notice>
              </PanelBody>
            )}
          </Panel>

          {/* Trend Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <PlotFrame
              title="ピーク位置推移 (2θ)"
              subtitle="点をクリックすると波形検証へ移動"
            >
              <PlotlyChart
                data={trendCenterTraces}
                layout={{
                  xaxis: { title: 'フレーム番号' },
                  yaxis: { title: '2θ [deg]' },
                  margin: { t: 16, r: 16, b: 42, l: 56 },
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

            <PlotFrame
              title="積分強度推移 (I)"
              subtitle="点をクリックすると波形検証へ移動"
            >
              <PlotlyChart
                data={trendIntensityTraces}
                layout={{
                  xaxis: { title: 'フレーム番号' },
                  yaxis: { title: '積分強度' },
                  margin: { t: 16, r: 16, b: 42, l: 56 },
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

          <PlotFrame
            title="相対残差 (Relative Residual) 推移"
            subtitle="赤: 外れ値判定フレーム / クリックで該当波形を開く"
          >
            <PlotlyChart
              data={trendResidualTraces}
              layout={{
                xaxis: { title: 'フレーム番号' },
                yaxis: { title: '相対残差 [-]' },
                margin: { t: 16, r: 16, b: 42, l: 56 },
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

          {/* Summary Table */}
          <Panel>
            <PanelHeader
              title="フィッティングパラメータ一覧"
              subtitle={`${activeGroup.sheet_name} (${activeGroup.rows.length}行)`}
            />
            <div className="max-h-[320px] overflow-auto">
              <table className="w-full text-[11px] font-mono tabular-nums border-collapse">
                <thead className="sticky top-0 bg-[#121418] border-b border-[#23262e] text-[#787f90]">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">#</th>
                    <th className="text-left px-3 py-2 font-medium">状態</th>
                    <th className="text-right px-3 py-2 font-medium">相対残差</th>
                    {activeGroup.peaks.map((pk) => (
                      <React.Fragment key={pk}>
                        <th className="text-right px-3 py-2 font-medium">2θ ({pk})</th>
                        <th className="text-right px-3 py-2 font-medium">I ({pk})</th>
                        <th className="text-right px-3 py-2 font-medium">FWHM ({pk})</th>
                      </React.Fragment>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1d24]">
                  {activeGroup.rows.map((row) => {
                    const isOutlier = outlierSet.has(row.num);
                    return (
                      <tr
                        key={row.num}
                        onClick={() => {
                          setInspectNum(row.num);
                          setActiveSubView('outlier_studio');
                        }}
                        className="hover:bg-[#1c1f26] cursor-pointer text-[#b4b9c4]"
                      >
                        <td className="px-3 py-1.5 text-[#eceef2]">{row.num}</td>
                        <td className="px-3 py-1.5">
                          {isOutlier ? (
                            <span className="text-[#f59e0b]">外れ値</span>
                          ) : (
                            <span className="text-[#34d399]">正常</span>
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
