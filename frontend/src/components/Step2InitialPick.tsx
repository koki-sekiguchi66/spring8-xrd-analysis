import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  RefreshCw,
  ArrowRight,
  FileSpreadsheet,
  Plus,
  Layers,
  CheckSquare,
  Square,
  ZoomIn,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { Button } from './ui/Button';
import { Panel, PanelBody, PanelHeader } from './ui/Panel';
import { SegmentedControl } from './ui/SegmentedControl';
import { PlotFrame } from './ui/PlotFrame';
import { TextInput, UnitNumberInput } from './ui/Field';
import { StatusBadge } from './ui/StatusBadge';
import { Notice } from './ui/Notice';
import { apiPost, fmtFixed } from '../lib/utils';
import type {
  CandidateFitResult,
  CandidateGroup,
  GroupBatchConfig,
  InitialAutoDetectResponse,
  PeakFitParam,
} from '../types/xrd';

export interface Step2InitialPickProps {
  folderPath: string;
  specimenName: string;
  initialData: InitialAutoDetectResponse | null;
  setInitialData: React.Dispatch<React.SetStateAction<InitialAutoDetectResponse | null>>;
  onConfirmInitialAndProceed: (batchConfigs: GroupBatchConfig[], savedExcelPath: string) => void;
}

type Step2SubScreen = 'overview' | 'detail';

export const Step2InitialPick: React.FC<Step2InitialPickProps> = ({
  folderPath,
  specimenName,
  initialData,
  setInitialData,
  onConfirmInitialAndProceed,
}) => {
  const [subScreen, setSubScreen] = useState<Step2SubScreen>('overview');
  const [focusedGroupId, setFocusedGroupId] = useState<string>('fcc200');

  const [mode, setMode] = useState<'auto' | 'manual'>('auto');
  const [manualInput, setManualInput] = useState<string>('50, 900');
  const [varyY0] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [savingExcel, setSavingExcel] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [activeProfileNum, setActiveProfileNum] = useState<number>(50);
  const [refittingGroupId, setRefittingGroupId] = useState<string | null>(null);

  const [rangeEdits, setRangeEdits] = useState<
    Record<string, { min: number; max: number; centers: number[] }>
  >({});

  const runDetection = useCallback(
    async (targetMode: 'auto' | 'manual', customNums?: number[]) => {
      if (!folderPath) return;
      setLoading(true);
      setError(null);
      try {
        const res = await apiPost<InitialAutoDetectResponse>('/api/initial/auto-detect', {
          folder_path: folderPath,
          mode: targetMode,
          manual_nums: customNums,
          vary_y0: varyY0,
        });
        setInitialData(res);
        if (res.selected_nums.length > 0) {
          setActiveProfileNum(res.selected_nums[res.selected_nums.length - 1]);
        }
        if (res.candidate_groups.length > 0) {
          setFocusedGroupId(res.candidate_groups[0].group_id);
        }
        const initRanges: Record<string, { min: number; max: number; centers: number[] }> = {};
        for (const g of res.candidate_groups) {
          const fit = g.fits_by_num[String(g.selected_num)];
          initRanges[g.group_id] = {
            min: g.range_min,
            max: g.range_max,
            centers: fit?.peaks ? fit.peaks.map((p) => p.xc) : [],
          };
        }
        setRangeEdits(initRanges);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [folderPath, varyY0, setInitialData]
  );

  useEffect(() => {
    if (!initialData && folderPath) {
      runDetection('auto');
    } else if (initialData && Object.keys(rangeEdits).length === 0) {
      const initRanges: Record<string, { min: number; max: number; centers: number[] }> = {};
      for (const g of initialData.candidate_groups) {
        const fit = g.fits_by_num[String(g.selected_num)];
        initRanges[g.group_id] = {
          min: g.range_min,
          max: g.range_max,
          centers: fit?.peaks ? fit.peaks.map((p) => p.xc) : [],
        };
      }
      setRangeEdits(initRanges);
      if (initialData.selected_nums.length > 0) {
        setActiveProfileNum(initialData.selected_nums[initialData.selected_nums.length - 1]);
      }
    }
  }, [initialData, folderPath, runDetection, rangeEdits]);

  const handleManualRun = () => {
    const nums = manualInput
      .split(/[,;\s]+/)
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !Number.isNaN(n) && n > 0);
    if (nums.length === 0) {
      setError('1つ以上のファイル番号（例: 50, 900）を指定してください。');
      return;
    }
    runDetection('manual', nums);
  };

  const handleToggleGroupSelected = (groupId: string, checked: boolean) => {
    if (!initialData) return;
    setInitialData({
      ...initialData,
      candidate_groups: initialData.candidate_groups.map((g) =>
        g.group_id === groupId ? { ...g, selected: checked } : g
      ),
    });
  };

  const handleChangeGroupNum = (groupId: string, numVal: number) => {
    if (!initialData) return;
    setInitialData({
      ...initialData,
      candidate_groups: initialData.candidate_groups.map((g) => {
        if (g.group_id !== groupId) return g;
        const fit = g.fits_by_num[String(numVal)];
        if (fit?.peaks) {
          setRangeEdits((prev) => ({
            ...prev,
            [groupId]: {
              min: fit.range_min,
              max: fit.range_max,
              centers: fit.peaks.map((p) => p.xc),
            },
          }));
        }
        return { ...g, selected_num: numVal };
      }),
    });
  };

  const handleRefitGroup = async (
    group: CandidateGroup,
    overrideMin?: number,
    overrideMax?: number
  ) => {
    if (!initialData) return;
    const edit = rangeEdits[group.group_id] || {
      min: group.range_min,
      max: group.range_max,
      centers: [],
    };
    const rMin = overrideMin !== undefined ? overrideMin : edit.min;
    const rMax = overrideMax !== undefined ? overrideMax : edit.max;

    setRefittingGroupId(group.group_id);
    setError(null);
    try {
      const fitRes = await apiPost<CandidateFitResult>('/api/initial/refit-single', {
        folder_path: folderPath,
        group_id: group.group_id,
        num: group.selected_num,
        peaks: group.peaks,
        range_min: rMin,
        range_max: rMax,
        initial_centers: edit.centers.length === group.peaks.length ? edit.centers : undefined,
        vary_y0: varyY0,
      });

      setInitialData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          candidate_groups: prev.candidate_groups.map((g) => {
            if (g.group_id !== group.group_id) return g;
            return {
              ...g,
              range_min: rMin,
              range_max: rMax,
              fits_by_num: {
                ...g.fits_by_num,
                [String(group.selected_num)]: fitRes,
              },
            };
          }),
        };
      });
      setRangeEdits((prev) => ({
        ...prev,
        [group.group_id]: {
          min: rMin,
          max: rMax,
          centers: fitRes.peaks.map((p) => p.xc),
        },
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefittingGroupId(null);
    }
  };

  const handleSaveAndProceed = async () => {
    if (!initialData) return;
    const chosenGroups = initialData.candidate_groups.filter((g) => g.selected);
    if (chosenGroups.length === 0) {
      setError('解析対象ピークを少なくとも1つ選択してください。');
      return;
    }

    const selectedPeakRows: PeakFitParam[] = [];
    const batchConfigs: GroupBatchConfig[] = [];

    for (const g of chosenGroups) {
      const fit = g.fits_by_num[String(g.selected_num)];
      if (!fit || !fit.peaks || fit.peaks.length === 0) continue;
      for (const pk of fit.peaks) {
        selectedPeakRows.push(pk);
      }

      const cFirst = fit.peaks[0].xc;
      const cLast = fit.peaks[fit.peaks.length - 1].xc;
      const p1Amp = Math.max(1e-3, fit.peaks[0].A);
      const p2Amp = fit.peaks.length > 1 ? fit.peaks[1].A : p1Amp * 0.5;

      batchConfigs.push({
        group_id: g.group_id,
        engine: g.default_engine,
        peaks: g.peaks,
        init_num: g.selected_num,
        init_peaks: fit.peaks,
        th_min: fit.range_min,
        th_max: fit.range_max,
        fitting_range_min: Number((fit.range_min - cFirst).toFixed(3)),
        fitting_range_max: Number((fit.range_max - cLast).toFixed(3)),
        dimt_onset_num: initialData.dimt_onset_estimate || 200,
        undeform_initial: 200,
        undeform_end: 275,
        R: Number((p2Amp / p1Amp).toFixed(4)),
        R2: 3.45,
        residual_limit: g.category === 'single' ? 0.7 : 180.0,
        max_attempts: 5,
        newly_forms_peak: g.peaks
          .map((pk, idx) => (pk.startsWith('bcc') ? idx : -1))
          .filter((idx) => idx >= 0),
        use_bcc211_constraint: true,
        bcc110_center_tol_deg: 0.05,
      });
    }

    setSavingExcel(true);
    setError(null);
    try {
      const saveRes = await apiPost<{ saved_path: string }>('/api/initial/save-excel', {
        folder_path: folderPath,
        specimen_name: specimenName,
        selected_peaks: selectedPeakRows,
      });
      onConfirmInitialAndProceed(batchConfigs, saveRes.saved_path);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingExcel(false);
    }
  };

  const activeProfile = initialData?.profiles_by_num[String(activeProfileNum)];

  const fullProfileTraces = useMemo(() => {
    if (!activeProfile) return [];
    const gammaMarkers = activeProfile.markers.filter((m) => m.phase === 'gamma');
    const alphaMarkers = activeProfile.markers.filter((m) => m.phase === 'alpha_prime');

    return [
      {
        x: activeProfile.x,
        y: activeProfile.y,
        type: 'scattergl',
        mode: 'lines',
        name: `#${activeProfile.num}`,
        line: { color: '#d4d8e0', width: 1.4 },
      },
      {
        x: gammaMarkers.map((m) => m.observed_2th),
        y: gammaMarkers.map((m) => m.intensity + 450),
        text: gammaMarkers.map((m) => `γ ${m.name}`),
        type: 'scatter',
        mode: 'markers+text',
        textposition: 'top center',
        textfont: { size: 11, color: '#38bdf8' },
        name: 'γ-FCC',
        marker: { color: '#38bdf8', size: 8, symbol: 'triangle-down' },
      },
      {
        x: alphaMarkers.map((m) => m.observed_2th),
        y: alphaMarkers.map((m) => m.intensity + 450),
        text: alphaMarkers.map((m) => `α' ${m.name}`),
        type: 'scatter',
        mode: 'markers+text',
        textposition: 'top center',
        textfont: { size: 11, color: '#f59e0b' },
        name: "α'-BCC",
        marker: { color: '#f59e0b', size: 8, symbol: 'diamond' },
      },
    ];
  }, [activeProfile]);

  const focusedGroup = useMemo(() => {
    if (!initialData) return null;
    return (
      initialData.candidate_groups.find((g) => g.group_id === focusedGroupId) ||
      initialData.candidate_groups[0] ||
      null
    );
  }, [initialData, focusedGroupId]);

  const focusedTraces = useMemo(() => {
    if (!focusedGroup) return [];
    const activeFit = focusedGroup.fits_by_num[String(focusedGroup.selected_num)];
    if (!activeFit || activeFit.error || !activeFit.x) return [];

    const traces: Record<string, unknown>[] = [
      {
        x: activeFit.x,
        y: activeFit.y_obs,
        type: 'scatter',
        mode: 'markers',
        name: `実測 (#${focusedGroup.selected_num})`,
        marker: { color: '#9ca3b0', size: 5 },
      },
      {
        x: activeFit.x,
        y: activeFit.y_fit,
        type: 'scatter',
        mode: 'lines',
        name: 'Voigt 合成',
        line: { color: '#f43f5e', width: 2.5 },
      },
    ];

    for (const pkName of focusedGroup.peaks) {
      const compY = activeFit.components?.[pkName];
      if (compY) {
        const isGamma = pkName.startsWith('fcc');
        traces.push({
          x: activeFit.x,
          y: compY,
          type: 'scatter',
          mode: 'lines',
          fill: 'tozeroy',
          name: pkName,
          line: {
            color: isGamma ? '#38bdf8' : '#f59e0b',
            width: 1.8,
            dash: 'dot',
          },
          fillcolor: isGamma ? 'rgba(56, 189, 248, 0.10)' : 'rgba(245, 158, 11, 0.10)',
        });
      }
    }

    traces.push({
      x: activeFit.x,
      y: activeFit.residual,
      type: 'scatter',
      mode: 'lines',
      name: '残差',
      line: { color: '#10b981', width: 1.4 },
      opacity: 0.85,
    });

    return traces;
  }, [focusedGroup]);

  return (
    <div className="space-y-4">
      {/* Compact Toolbar */}
      <Panel>
        <div className="px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <SegmentedControl
              ariaLabel="表示切替"
              value={subScreen}
              onChange={setSubScreen}
              options={[
                {
                  value: 'overview',
                  label: '全体・候補選択',
                  icon: <Layers className="size-3.5" aria-hidden="true" />,
                  accent: 'sky',
                },
                {
                  value: 'detail',
                  label: '拡大フィット調整',
                  icon: <ZoomIn className="size-3.5" aria-hidden="true" />,
                  accent: 'sky',
                },
              ]}
            />

            <SegmentedControl
              ariaLabel="代表ファイル選出モード"
              value={mode}
              onChange={(m) => {
                setMode(m);
                if (m === 'auto') runDetection('auto');
              }}
              options={[
                { value: 'auto', label: '自動選出', accent: 'neutral' },
                { value: 'manual', label: '手動指定', accent: 'amber' },
              ]}
            />

            {mode === 'manual' && (
              <div className="flex items-center gap-1.5">
                <TextInput
                  aria-label="手動指定するファイル番号"
                  mono
                  value={manualInput}
                  onChange={(e) => setManualInput(e.target.value)}
                  placeholder="50, 900"
                  className="w-32 tabular-nums"
                />
                <Button variant="amber" size="sm" onClick={handleManualRun}>
                  <Plus className="size-3.5" aria-hidden="true" />
                  <span>再探索</span>
                </Button>
              </div>
            )}

            {loading && (
              <span className="inline-flex items-center gap-1.5 text-xs font-mono text-sky-300">
                <RefreshCw className="size-3.5 animate-spin" aria-hidden="true" />
                <span>探索中...</span>
              </span>
            )}
          </div>

          <Button
            variant="emerald"
            size="sm"
            disabled={savingExcel || !initialData}
            onClick={handleSaveAndProceed}
            title={`${specimenName}_initial.xlsx を保存して Step 3 へ進みます`}
          >
            <FileSpreadsheet className="size-3.5" aria-hidden="true" />
            <span>
              {savingExcel
                ? '保存中...'
                : `${specimenName || '試料'}_initial.xlsx 保存`}
            </span>
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </Panel>

      {error && <Notice tone="error">{error}</Notice>}

      {/* SUB-SCREEN A: Full Profile & Candidate Grid */}
      {initialData && subScreen === 'overview' && (
        <div className="space-y-4">
          <PlotFrame
            title="全体回折プロファイル"
            subtitle={`#${activeProfileNum} / 変態開始推定 #${initialData.dimt_onset_estimate}`}
            toolbar={
              <div className="flex items-center gap-2 flex-wrap">
                <StatusBadge tone="sky" dot>
                  γ-FCC (5面)
                </StatusBadge>
                <StatusBadge tone="amber" dot>
                  α&apos;-BCC (4面)
                </StatusBadge>
                <div className="h-4 w-px bg-[#23262e]" />
                {initialData.selected_nums.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setActiveProfileNum(n)}
                    className={`h-6 px-2.5 rounded text-xs font-mono tabular-nums border transition-colors ${
                      activeProfileNum === n
                        ? 'bg-sky-500/15 border-sky-500/50 text-sky-300 font-semibold'
                        : 'bg-[#0a0b0e] border-[#23262e] text-[#9ca3b0] hover:text-[#eceef2]'
                    }`}
                  >
                    #{n}
                    {n === initialData.early_num
                      ? ' 初期'
                      : n === initialData.late_num
                      ? ' 後期'
                      : ''}
                  </button>
                ))}
              </div>
            }
          >
            <PlotlyChart
              data={fullProfileTraces}
              layout={{
                margin: { l: 56, r: 16, t: 16, b: 40 },
                xaxis: { title: '2θ (deg)', range: [10.5, 25.0] },
                yaxis: { title: 'Intensity (a.u.)', range: [-200, 18000] },
              }}
              className="w-full h-64"
            />
          </PlotFrame>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {initialData.candidate_groups.map((group) => {
              const activeFit = group.fits_by_num[String(group.selected_num)];
              const isMulti = group.category === 'multi_pair';

              return (
                <div
                  key={group.group_id}
                  className={`rounded-lg border p-3.5 flex flex-col justify-between gap-3 transition-colors ${
                    group.selected
                      ? isMulti
                        ? 'bg-[#16181d] border-amber-500/45'
                        : 'bg-[#16181d] border-sky-500/45'
                      : 'bg-[#121418] border-[#23262e] opacity-60'
                  }`}
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          handleToggleGroupSelected(group.group_id, !group.selected)
                        }
                        className="flex items-start gap-2 text-left min-w-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/60 rounded"
                      >
                        {group.selected ? (
                          <CheckSquare className="size-4 text-sky-400 shrink-0 mt-0.5" aria-hidden="true" />
                        ) : (
                          <Square className="size-4 text-[#636b78] shrink-0 mt-0.5" aria-hidden="true" />
                        )}
                        <div className="min-w-0">
                          <div className="text-[13px] font-semibold text-[#eceef2] truncate">
                            {group.label}
                          </div>
                          <div className="text-xs text-[#9ca3b0] truncate mt-0.5">
                            {group.description}
                          </div>
                        </div>
                      </button>

                      {activeFit && !activeFit.error && (
                        <StatusBadge
                          tone={activeFit.r_squared >= 0.99 ? 'emerald' : 'neutral'}
                          mono
                        >
                          R² {fmtFixed(activeFit.r_squared, 4)}
                        </StatusBadge>
                      )}
                    </div>

                    <div className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded bg-[#0a0b0e] border border-[#23262e]">
                      <span className="text-[11px] text-[#636b78]">代表ファイル</span>
                      <div className="flex items-center gap-1">
                        {initialData.selected_nums.map((numOpt) => (
                          <button
                            key={numOpt}
                            type="button"
                            onClick={() => handleChangeGroupNum(group.group_id, numOpt)}
                            className={`h-5 px-2 rounded text-[11px] font-mono tabular-nums transition-colors ${
                              group.selected_num === numOpt
                                ? 'bg-sky-500 text-zinc-950 font-semibold'
                                : 'bg-[#16181d] text-[#9ca3b0] hover:text-[#eceef2]'
                            }`}
                          >
                            #{numOpt}
                            {numOpt === group.recommended_num ? '*' : ''}
                          </button>
                        ))}
                      </div>
                    </div>

                    {activeFit && activeFit.peaks && (
                      <div className="space-y-1 px-2.5 py-2 rounded bg-[#0a0b0e] border border-[#23262e] font-mono text-xs tabular-nums">
                        {activeFit.peaks.map((pk) => {
                          const isGamma = pk.peak_name.startsWith('fcc');
                          return (
                            <div
                              key={pk.peak_name}
                              className="flex items-center justify-between gap-2"
                            >
                              <span
                                className={`font-semibold ${
                                  isGamma ? 'text-sky-300' : 'text-amber-300'
                                }`}
                              >
                                {pk.peak_name}
                              </span>
                              <span className="text-[#9ca3b0]">
                                {fmtFixed(pk.xc, 3)}° · A={fmtFixed(pk.A, 0)} · W={fmtFixed(pk.FWHM, 4)}°
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <Button
                    variant="secondary"
                    size="xs"
                    block
                    onClick={() => {
                      setFocusedGroupId(group.group_id);
                      setSubScreen('detail');
                    }}
                  >
                    <ZoomIn className="size-3.5 text-sky-400" aria-hidden="true" />
                    <span>拡大フィット調整</span>
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* SUB-SCREEN B: Focused Single-Group Inspector */}
      {initialData && subScreen === 'detail' && focusedGroup && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          <Panel className="lg:col-span-3">
            <PanelHeader title="ピークグループ" />
            <div className="p-2 space-y-1">
              {initialData.candidate_groups.map((g) => {
                const isCurrent = g.group_id === focusedGroup.group_id;
                const fit = g.fits_by_num[String(g.selected_num)];
                return (
                  <div
                    key={g.group_id}
                    className={`px-2.5 py-2 rounded-md border flex items-center justify-between gap-2 transition-colors ${
                      isCurrent
                        ? 'bg-[#1c1f26] border-sky-500/50 text-[#eceef2]'
                        : 'bg-transparent border-transparent text-[#9ca3b0] hover:bg-[#16181d]'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <input
                        type="checkbox"
                        aria-label={`${g.label} を解析対象に含める`}
                        checked={g.selected}
                        onChange={(e) => handleToggleGroupSelected(g.group_id, e.target.checked)}
                        className="size-3.5 rounded border-[#313642] bg-[#0a0b0e] accent-sky-500 shrink-0"
                      />
                      <button
                        type="button"
                        onClick={() => setFocusedGroupId(g.group_id)}
                        className="text-left min-w-0 flex-1 truncate"
                      >
                        <div className="text-[13px] font-medium truncate">{g.label}</div>
                        <div className="text-[11px] font-mono text-[#636b78]">
                          #{g.selected_num}
                        </div>
                      </button>
                    </div>
                    {fit && !fit.error && (
                      <span className="text-[11px] font-mono tabular-nums text-emerald-300 shrink-0">
                        {fmtFixed(fit.r_squared, 4)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel className="lg:col-span-9">
            {(() => {
              const activeFit = focusedGroup.fits_by_num[String(focusedGroup.selected_num)];
              const editState = rangeEdits[focusedGroup.group_id] || {
                min: focusedGroup.range_min,
                max: focusedGroup.range_max,
                centers: activeFit?.peaks?.map((p) => p.xc) ?? [],
              };

              return (
                <>
                  <PanelHeader
                    title={focusedGroup.label}
                    subtitle={focusedGroup.description}
                    actions={
                      <div className="flex items-center gap-1 bg-[#0a0b0e] border border-[#23262e] rounded-md p-0.5">
                        {initialData.selected_nums.map((numOpt) => (
                          <button
                            key={numOpt}
                            type="button"
                            onClick={() => handleChangeGroupNum(focusedGroup.group_id, numOpt)}
                            className={`h-6 px-2.5 rounded text-xs font-mono tabular-nums transition-colors ${
                              focusedGroup.selected_num === numOpt
                                ? 'bg-sky-500 text-zinc-950 font-semibold'
                                : 'text-[#9ca3b0] hover:text-[#eceef2]'
                            }`}
                          >
                            #{numOpt}
                          </button>
                        ))}
                      </div>
                    }
                  />
                  <PanelBody className="space-y-4">
                    <div className="rounded-md bg-[#0a0b0e] border border-[#23262e] p-2">
                      <PlotlyChart
                        data={focusedTraces}
                        layout={{
                          margin: { l: 54, r: 16, t: 14, b: 40 },
                          xaxis: { title: '2θ (deg)' },
                          yaxis: { title: 'Intensity (a.u.)' },
                        }}
                        className="w-full h-[340px]"
                        onRangeSelect={(rMin, rMax) => {
                          setRangeEdits((prev) => ({
                            ...prev,
                            [focusedGroup.group_id]: {
                              ...(prev[focusedGroup.group_id] || { centers: [] }),
                              min: Number(rMin.toFixed(4)),
                              max: Number(rMax.toFixed(4)),
                            },
                          }));
                        }}
                      />
                    </div>

                    {activeFit && activeFit.peaks && (
                      <div className="overflow-x-auto rounded-md bg-[#0a0b0e] border border-[#23262e]">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="border-b border-[#23262e] bg-[#121418] text-[#9ca3b0]">
                              <th className="py-2 px-3 font-medium">Peak</th>
                              <th className="py-2 px-3 font-medium">No</th>
                              <th className="py-2 px-3 font-medium text-right">xc (2θ°)</th>
                              <th className="py-2 px-3 font-medium text-right">面積強度 A</th>
                              <th className="py-2 px-3 font-medium text-right">wG (°)</th>
                              <th className="py-2 px-3 font-medium text-right">wL (°)</th>
                              <th className="py-2 px-3 font-medium text-right">FWHM (°)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#1e2129] font-mono tabular-nums">
                            {activeFit.peaks.map((pk, idx) => {
                              const isGamma = pk.peak_name.startsWith('fcc');
                              return (
                                <tr key={pk.peak_name} className="hover:bg-[#16181d]">
                                  <td className="py-2 px-3 font-semibold">
                                    <span className={isGamma ? 'text-sky-300' : 'text-amber-300'}>
                                      {pk.peak_name}
                                    </span>
                                  </td>
                                  <td className="py-2 px-3 text-[#9ca3b0]">{pk.No}</td>
                                  <td className="py-1.5 px-3 text-right">
                                    <input
                                      type="number"
                                      step="0.005"
                                      value={editState.centers[idx] ?? pk.xc}
                                      onChange={(e) => {
                                        const val = Number(e.target.value);
                                        const nextCenters = [
                                          ...(editState.centers || activeFit.peaks.map((p) => p.xc)),
                                        ];
                                        nextCenters[idx] = val;
                                        setRangeEdits((prev) => ({
                                          ...prev,
                                          [focusedGroup.group_id]: {
                                            ...editState,
                                            centers: nextCenters,
                                          },
                                        }));
                                      }}
                                      className="w-24 h-7 bg-[#16181d] border border-[#2a2e38] rounded px-2 text-right text-xs font-mono tabular-nums text-[#eceef2] focus:border-sky-500/70 focus:outline-none"
                                    />
                                  </td>
                                  <td className="py-2 px-3 text-right text-[#eceef2]">
                                    {fmtFixed(pk.A, 2)}
                                  </td>
                                  <td className="py-2 px-3 text-right text-[#9ca3b0]">
                                    {fmtFixed(pk.wG, 5)}
                                  </td>
                                  <td className="py-2 px-3 text-right text-[#9ca3b0]">
                                    {fmtFixed(pk.wL, 5)}
                                  </td>
                                  <td className="py-2 px-3 text-right font-semibold text-emerald-300">
                                    {fmtFixed(pk.FWHM, 5)}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-medium text-[#9ca3b0]">2θ 範囲</span>
                        <UnitNumberInput
                          step="0.05"
                          unit="deg"
                          value={editState.min}
                          onChange={(e) =>
                            setRangeEdits((prev) => ({
                              ...prev,
                              [focusedGroup.group_id]: {
                                ...editState,
                                min: Number(e.target.value),
                              },
                            }))
                          }
                          className="w-28"
                        />
                        <span className="text-xs text-[#636b78]">–</span>
                        <UnitNumberInput
                          step="0.05"
                          unit="deg"
                          value={editState.max}
                          onChange={(e) =>
                            setRangeEdits((prev) => ({
                              ...prev,
                              [focusedGroup.group_id]: {
                                ...editState,
                                max: Number(e.target.value),
                              },
                            }))
                          }
                          className="w-28"
                        />
                      </div>

                      <Button
                        variant="primary"
                        size="sm"
                        disabled={refittingGroupId === focusedGroup.group_id}
                        onClick={() => handleRefitGroup(focusedGroup)}
                      >
                        <RefreshCw
                          className={`size-3.5 ${
                            refittingGroupId === focusedGroup.group_id ? 'animate-spin' : ''
                          }`}
                          aria-hidden="true"
                        />
                        <span>再フィット</span>
                      </Button>
                    </div>
                  </PanelBody>
                </>
              );
            })()}
          </Panel>
        </div>
      )}
    </div>
  );
};
