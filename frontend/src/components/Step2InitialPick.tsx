import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Sparkles,
  RefreshCw,
  ArrowRight,
  FileSpreadsheet,
  Sliders,
  Plus,
  AlertTriangle,
  Layers,
  CheckSquare,
  Square,
  ZoomIn,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { TutorialGuideBanner } from './TutorialGuideBanner';
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
  const [varyY0, setVaryY0] = useState<boolean>(false);
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
      setError('手動指定モードでは1つ以上のファイル番号 (例: 50, 900) を入力してください。');
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
      setError('連続解析を実行するピークまたはペアを少なくとも1つ選択してください。');
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
        name: `Profile #${activeProfile.num} (${activeProfile.filename})`,
        line: { color: '#e4e4e7', width: 1.5 },
      },
      {
        x: gammaMarkers.map((m) => m.observed_2th),
        y: gammaMarkers.map((m) => m.intensity + 450),
        text: gammaMarkers.map((m) => `γ ${m.name} (${fmtFixed(m.observed_2th, 2)}°)`),
        type: 'scatter',
        mode: 'markers+text',
        textposition: 'top center',
        textfont: { size: 12, color: '#22d3ee' },
        name: 'γ-FCC Austenite (オーステナイト相)',
        marker: { color: '#06b6d4', size: 10, symbol: 'triangle-down' },
      },
      {
        x: alphaMarkers.map((m) => m.observed_2th),
        y: alphaMarkers.map((m) => m.intensity + 450),
        text: alphaMarkers.map((m) => `α' ${m.name} (${fmtFixed(m.observed_2th, 2)}°)`),
        type: 'scatter',
        mode: 'markers+text',
        textposition: 'top center',
        textfont: { size: 12, color: '#fbbf24' },
        name: "α'-BCC Martensite (マルテンサイト相)",
        marker: { color: '#f59e0b', size: 10, symbol: 'diamond' },
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
        name: `実測データ (#${focusedGroup.selected_num})`,
        marker: { color: '#a1a1aa', size: 6 },
      },
      {
        x: activeFit.x,
        y: activeFit.y_fit,
        type: 'scatter',
        mode: 'lines',
        name: 'Origin互換 Voigt 合成フィット',
        line: { color: '#f43f5e', width: 2.8 },
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
          name: `${pkName} (${isGamma ? 'γ-FCC' : "α'-BCC"})`,
          line: {
            color: isGamma ? '#06b6d4' : '#f59e0b',
            width: 2,
            dash: 'dot',
          },
          fillcolor: isGamma ? 'rgba(6, 182, 212, 0.12)' : 'rgba(245, 158, 11, 0.12)',
        });
      }
    }

    traces.push({
      x: activeFit.x,
      y: activeFit.residual,
      type: 'scatter',
      mode: 'lines',
      name: '残差 Residual',
      line: { color: '#10b981', width: 1.5 },
      opacity: 0.85,
    });

    return traces;
  }, [focusedGroup]);

  return (
    <div className="space-y-6">
      {/* Beginner Tutorial Banner */}
      <TutorialGuideBanner
        mode="xrd"
        stepTitle="Step 2: 複数ファイル初期値探索 ＆ 面指数自動同定（Origin完全互換Voigt）"
        summary="変形初期（オーステナイト単相 #50）と変形後期（マルテンサイト生成後 #900）の2つの代表ファイルから、各ピークの初期値を自動算出します。"
        steps={[
          {
            badge: 'STEP 1',
            title: '連続解析したいピーク・重畳ペアにチェックを入れる',
            description:
              '下のカード一覧から、連続フィッティングしたいピーク（例: fcc200、fcc111+bcc110、bcc211 など）にチェックを入れます。',
          },
          {
            badge: 'STEP 2',
            title: '必要に応じて「② 拡大フィット確認・微調整」で波形を確認',
            description:
              '各カードの「拡大確認・微調整」を押すと、大画面で1つのピークのVoigt成分分離波形を確認・調整できます。',
          },
          {
            badge: 'STEP 3',
            title: '_initial.xlsx に保存して Step 3（連続フィッティング）へ進む',
            description:
              '緑色の「採用初期値を _initial.xlsx に保存して Step 3 へ進む」ボタンを押すと初期値ファイルが自動生成されます。',
          },
        ]}
        glossary={[
          {
            term: 'なぜ変形初期 (#50) と変形後期 (#900) の2ファイルを使うの？',
            meaning:
              '変形初期はオーステナイト相（γ-FCC）が強く孤立しており、変形後期は加工誘起マルテンサイト相（α\'-BCC）が明瞭に現れるため、両方を見ることで全ピークの正確な初期値が得られます。',
          },
          {
            term: 'Origin完全互換Voigt関数 (wG, wL, FWHM) とは？',
            meaning:
              'ガウス幅 wG とローレンツ幅 wL を独立変数として最適化し、Originと同じ Olivero-Longbothum 近似式で合成半値幅 FWHM を算出します。',
          },
        ]}
      />

      {/* Top Mode & Sub-Screen Switch Bar */}
      <section className="panel-card p-5 flex flex-wrap items-center justify-between gap-4">
        <div data-tour="step2-subscreen-tabs" className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => setSubScreen('overview')}
            className={`px-5 py-3 rounded-xl text-sm sm:text-base font-bold transition-all flex items-center gap-2 ${
              subScreen === 'overview'
                ? 'bg-cyan-500 text-zinc-950 shadow-md shadow-cyan-500/20'
                : 'bg-zinc-800/90 text-zinc-200 hover:bg-zinc-700'
            }`}
          >
            <Layers className="w-5 h-5" />
            <span>① 全体プロファイル ＆ 解析ピーク候補の選択</span>
          </button>

          <button
            type="button"
            onClick={() => setSubScreen('detail')}
            className={`px-5 py-3 rounded-xl text-sm sm:text-base font-bold transition-all flex items-center gap-2 ${
              subScreen === 'detail'
                ? 'bg-cyan-500 text-zinc-950 shadow-md shadow-cyan-500/20'
                : 'bg-zinc-800/90 text-zinc-200 hover:bg-zinc-700'
            }`}
          >
            <ZoomIn className="w-5 h-5" />
            <span>② 個別ピーク拡大Voigtフィット確認・微調整</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Auto / Manual Switch */}
          <div className="inline-flex rounded-xl bg-zinc-950 p-1 border border-zinc-800">
            <button
              type="button"
              onClick={() => {
                setMode('auto');
                runDetection('auto');
              }}
              className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-colors ${
                mode === 'auto'
                  ? 'bg-cyan-500 text-zinc-950'
                  : 'text-zinc-300 hover:text-white'
              }`}
            >
              自動選出 (初期γ + 後期γ+α&apos;)
            </button>
            <button
              type="button"
              onClick={() => setMode('manual')}
              className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-semibold transition-colors ${
                mode === 'manual'
                  ? 'bg-amber-500 text-zinc-950'
                  : 'text-zinc-300 hover:text-white'
              }`}
            >
              手動 `num` 指定
            </button>
          </div>

          {mode === 'manual' && (
            <div className="flex items-center gap-2">
              <input
                type="text"
                aria-label="手動指定するファイル番号リスト"
                value={manualInput}
                onChange={(e) => setManualInput(e.target.value)}
                placeholder="50, 200, 900"
                className="w-40 input-field py-2 text-sm font-mono tabular-nums"
              />
              <button
                type="button"
                onClick={handleManualRun}
                className="btn-amber py-2 px-3.5 text-sm"
              >
                <Plus className="w-4 h-4" />
                <span>再探索</span>
              </button>
            </div>
          )}

          <button
            type="button"
            data-tour="step2-save-proceed-btn"
            disabled={savingExcel || !initialData}
            onClick={handleSaveAndProceed}
            className="btn-emerald"
          >
            <FileSpreadsheet className="w-5 h-5" />
            <span>
              {savingExcel
                ? '初期値Excel生成中...'
                : `採用初期値を ${specimenName}_initial.xlsx に保存して Step 3 へ`}
            </span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {error && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-rose-950/60 border border-rose-500/40 text-sm text-rose-200 flex items-center gap-2.5"
        >
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* =====================================================================
          SUB-SCREEN 2-A: Full Profile + Clean Peak Candidate Selection Grid
         ===================================================================== */}
      {initialData && subScreen === 'overview' && (
        <div className="space-y-6">
          {/* Full Diffraction Profile Card */}
          <section className="panel-card p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3 flex-wrap">
                <h3 className="text-lg font-bold text-zinc-100 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-cyan-400" />
                  全体回折プロファイル ＆ 結晶学的面指数自動同定 (9面指数)
                </h3>
                <span className="px-2.5 py-1 rounded-lg bg-cyan-950/70 border border-cyan-500/40 text-xs font-mono text-cyan-200">
                  γ-FCC: fcc111, fcc200, fcc220, fcc311, fcc222
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-amber-950/70 border border-amber-500/40 text-xs font-mono text-amber-200">
                  α&apos;-BCC: bcc110, bcc200, bcc211, bcc220
                </span>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-zinc-300">表示代表ファイル:</span>
                {initialData.selected_nums.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setActiveProfileNum(n)}
                    className={`px-3.5 py-1.5 rounded-lg text-sm font-mono tabular-nums border transition-colors ${
                      activeProfileNum === n
                        ? 'bg-cyan-500/25 border-cyan-400 text-cyan-200 font-bold'
                        : 'bg-zinc-950 border-zinc-800 text-zinc-300 hover:text-white'
                    }`}
                  >
                    num=#{n}{' '}
                    {n === initialData.early_num
                      ? '(変形初期 γ単相)'
                      : n === initialData.late_num
                      ? "(変形後期 γ+α'二相)"
                      : ''}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-2">
              <PlotlyChart
                data={fullProfileTraces}
                layout={{
                  title: {
                    text: `全体XRD回折プロファイル — num=#${activeProfileNum} (推定マルテンサイト変態開始: num≈#${initialData.dimt_onset_estimate})`,
                    font: { size: 14, color: '#e4e4e7' },
                  },
                  xaxis: { title: '回折角 2θ (deg.)', range: [10.5, 25.0] },
                  yaxis: { title: '強度 Intensity (a.u.)', range: [-200, 18000] },
                }}
                className="w-full h-72"
              />
            </div>
          </section>

          {/* Clean Candidate Selection Grid */}
          <section data-tour="step2-candidate-cards" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-bold text-zinc-100">
                解析対象ピーク・重畳ペアの選択（チェックを入れた項目を連続解析します）
              </h3>
              <span className="text-sm text-zinc-300">
                各カードの「拡大確認・微調整」を押すと大画面でVoigtフィット波形を調整できます
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {initialData.candidate_groups.map((group) => {
                const activeFit = group.fits_by_num[String(group.selected_num)];
                const isMulti = group.category === 'multi_pair';

                return (
                  <div
                    key={group.group_id}
                    className={`rounded-xl border p-5 flex flex-col justify-between gap-4 transition-all ${
                      group.selected
                        ? isMulti
                          ? 'bg-zinc-900/95 border-amber-500/60 shadow-lg'
                          : 'bg-zinc-900/95 border-cyan-500/60 shadow-lg'
                        : 'bg-zinc-900/40 border-zinc-800 opacity-75'
                    }`}
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <button
                          type="button"
                          onClick={() =>
                            handleToggleGroupSelected(group.group_id, !group.selected)
                          }
                          className="flex items-start gap-3 text-left"
                        >
                          {group.selected ? (
                            <CheckSquare className="w-6 h-6 text-cyan-400 shrink-0 mt-0.5" />
                          ) : (
                            <Square className="w-6 h-6 text-zinc-500 shrink-0 mt-0.5" />
                          )}
                          <div>
                            <div className="text-base sm:text-lg font-bold text-zinc-100">
                              {group.label}
                            </div>
                            <p className="text-xs sm:text-sm text-zinc-300 mt-0.5">
                              {group.description}
                            </p>
                          </div>
                        </button>

                        {activeFit && !activeFit.error && (
                          <span
                            className={`px-2.5 py-1 rounded-lg text-xs font-mono tabular-nums font-bold shrink-0 ${
                              activeFit.r_squared >= 0.99
                                ? 'bg-emerald-950/90 border border-emerald-500/40 text-emerald-300'
                                : 'bg-zinc-800 text-zinc-200'
                            }`}
                          >
                            R² = {fmtFixed(activeFit.r_squared, 4)}
                          </span>
                        )}
                      </div>

                      {/* Source num radio */}
                      <div className="flex flex-wrap items-center gap-2 bg-zinc-950 border border-zinc-800 rounded-lg p-2.5">
                        <span className="text-xs font-medium text-zinc-400">採用代表ファイル:</span>
                        {initialData.selected_nums.map((numOpt) => (
                          <button
                            key={numOpt}
                            type="button"
                            onClick={() => handleChangeGroupNum(group.group_id, numOpt)}
                            className={`px-2.5 py-1 rounded-md text-xs font-mono tabular-nums transition-colors ${
                              group.selected_num === numOpt
                                ? 'bg-cyan-500 text-zinc-950 font-bold'
                                : 'bg-zinc-900 text-zinc-300 hover:text-white'
                            }`}
                          >
                            #{numOpt}
                            {numOpt === group.recommended_num && ' (推奨)'}
                          </button>
                        ))}
                      </div>

                      {/* Compact Parameter Summary */}
                      {activeFit && activeFit.peaks && (
                        <div className="space-y-1.5 bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-3 font-mono text-xs sm:text-sm tabular-nums">
                          {activeFit.peaks.map((pk) => {
                            const isGamma = pk.peak_name.startsWith('fcc');
                            return (
                              <div
                                key={pk.peak_name}
                                className="flex items-center justify-between gap-2"
                              >
                                <span
                                  className={`font-bold ${
                                    isGamma ? 'text-cyan-300' : 'text-amber-300'
                                  }`}
                                >
                                  {pk.peak_name}
                                </span>
                                <span className="text-zinc-200">
                                  2θ={fmtFixed(pk.xc, 3)}° | A={fmtFixed(pk.A, 0)} | FWHM=
                                  {fmtFixed(pk.FWHM, 4)}°
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setFocusedGroupId(group.group_id);
                        setSubScreen('detail');
                      }}
                      className="btn-secondary w-full py-2 text-sm"
                    >
                      <ZoomIn className="w-4 h-4 text-cyan-400" />
                      <span>拡大Voigtフィット波形を確認・微調整 ▶</span>
                    </button>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      )}

      {/* =====================================================================
          SUB-SCREEN 2-B: Focused Single-Group Large Voigt Fit Inspector
         ===================================================================== */}
      {initialData && subScreen === 'detail' && focusedGroup && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Group Selector List */}
          <div className="lg:col-span-4 panel-card p-5 space-y-3">
            <h3 className="text-base font-bold text-zinc-100 border-b border-zinc-800 pb-3">
              確認・微調整するピーク候補を選択
            </h3>
            <div className="space-y-2">
              {initialData.candidate_groups.map((g) => {
                const isCurrent = g.group_id === focusedGroup.group_id;
                const fit = g.fits_by_num[String(g.selected_num)];
                return (
                  <div
                    key={g.group_id}
                    onClick={() => setFocusedGroupId(g.group_id)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between gap-2 ${
                      isCurrent
                        ? 'bg-cyan-500/20 border-cyan-400 text-zinc-100'
                        : 'bg-zinc-950/70 border-zinc-800 text-zinc-300 hover:bg-zinc-800/60'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <input
                        type="checkbox"
                        checked={g.selected}
                        onChange={(e) => {
                          e.stopPropagation();
                          handleToggleGroupSelected(g.group_id, e.target.checked);
                        }}
                        className="w-4 h-4 rounded border-zinc-600 text-cyan-500"
                      />
                      <div className="truncate">
                        <div className="text-sm font-bold truncate">{g.label}</div>
                        <div className="text-xs text-zinc-400 font-mono">
                          採用ファイル: #{g.selected_num}
                        </div>
                      </div>
                    </div>
                    {fit && !fit.error && (
                      <span className="text-xs font-mono tabular-nums text-emerald-300 shrink-0">
                        R²={fmtFixed(fit.r_squared, 4)}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Large Voigt Fit Plot & Editable Parameter Table */}
          <div className="lg:col-span-8 panel-card p-6 space-y-5">
            {(() => {
              const activeFit = focusedGroup.fits_by_num[String(focusedGroup.selected_num)];
              const editState = rangeEdits[focusedGroup.group_id] || {
                min: focusedGroup.range_min,
                max: focusedGroup.range_max,
                centers: activeFit?.peaks?.map((p) => p.xc) ?? [],
              };

              return (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4">
                    <div>
                      <h3 className="text-xl font-bold text-zinc-100">{focusedGroup.label}</h3>
                      <p className="text-sm text-zinc-300 mt-0.5">{focusedGroup.description}</p>
                    </div>

                    <div className="flex items-center gap-2 bg-zinc-950 border border-zinc-800 rounded-xl px-3.5 py-2">
                      <span className="text-sm text-zinc-300 mr-1">初期値採用ファイル:</span>
                      {initialData.selected_nums.map((numOpt) => (
                        <button
                          key={numOpt}
                          type="button"
                          onClick={() => handleChangeGroupNum(focusedGroup.group_id, numOpt)}
                          className={`px-3 py-1 rounded-lg text-sm font-mono tabular-nums ${
                            focusedGroup.selected_num === numOpt
                              ? 'bg-cyan-500 text-zinc-950 font-bold'
                              : 'text-zinc-300 hover:text-white'
                          }`}
                        >
                          #{numOpt}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Large Interactive Voigt Fit & Residual Chart */}
                  <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-2">
                    <PlotlyChart
                      data={focusedTraces}
                      layout={{
                        xaxis: { title: '回折角 2θ (deg.)' },
                        yaxis: { title: '強度 Intensity (a.u.)' },
                      }}
                      className="w-full h-[380px]"
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

                  {/* Parameter Table */}
                  {activeFit && activeFit.peaks && (
                    <div className="overflow-x-auto bg-zinc-950 border border-zinc-800 rounded-xl">
                      <table className="w-full text-left border-collapse text-sm">
                        <thead>
                          <tr className="border-b border-zinc-800 bg-zinc-900 text-zinc-300 font-mono">
                            <th className="py-2.5 px-4">Peak</th>
                            <th className="py-2.5 px-3">No</th>
                            <th className="py-2.5 px-3 text-right">初期中心角 xc (2θ°)</th>
                            <th className="py-2.5 px-3 text-right">積分強度 A</th>
                            <th className="py-2.5 px-3 text-right">ガウス幅 wG (°)</th>
                            <th className="py-2.5 px-3 text-right">ローレンツ幅 wL (°)</th>
                            <th className="py-2.5 px-4 text-right">合成半値幅 FWHM (°)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-800/60 font-mono tabular-nums">
                          {activeFit.peaks.map((pk, idx) => {
                            const isGamma = pk.peak_name.startsWith('fcc');
                            return (
                              <tr key={pk.peak_name} className="hover:bg-zinc-900/40">
                                <td className="py-2.5 px-4 font-bold">
                                  <span className={isGamma ? 'text-cyan-400' : 'text-amber-400'}>
                                    {pk.peak_name}
                                  </span>
                                </td>
                                <td className="py-2.5 px-3 text-zinc-300">{pk.No}</td>
                                <td className="py-2.5 px-3 text-right">
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
                                    className="w-28 bg-zinc-900 border border-zinc-700 rounded-lg px-2.5 py-1 text-right text-sm font-mono tabular-nums text-zinc-100"
                                  />
                                </td>
                                <td className="py-2.5 px-3 text-right text-zinc-200">
                                  {fmtFixed(pk.A, 2)}
                                </td>
                                <td className="py-2.5 px-3 text-right text-zinc-300">
                                  {fmtFixed(pk.wG, 5)}
                                </td>
                                <td className="py-2.5 px-3 text-right text-zinc-300">
                                  {fmtFixed(pk.wL, 5)}
                                </td>
                                <td className="py-2.5 px-4 text-right font-bold text-emerald-400">
                                  {fmtFixed(pk.FWHM, 5)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Range Fine-Tuning & Refit Action */}
                  <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
                    <div className="flex items-center gap-3 flex-wrap">
                      <Sliders className="w-4 h-4 text-cyan-400" />
                      <span className="text-sm font-medium text-zinc-200">
                        フィッティング範囲 2θ (deg):
                      </span>
                      <input
                        type="number"
                        step="0.05"
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
                        className="w-28 input-field py-1.5 text-sm font-mono tabular-nums"
                      />
                      <span className="text-zinc-400">〜</span>
                      <input
                        type="number"
                        step="0.05"
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
                        className="w-28 input-field py-1.5 text-sm font-mono tabular-nums"
                      />
                    </div>

                    <button
                      type="button"
                      disabled={refittingGroupId === focusedGroup.group_id}
                      onClick={() => handleRefitGroup(focusedGroup)}
                      className="btn-primary"
                    >
                      <RefreshCw
                        className={`w-4 h-4 ${
                          refittingGroupId === focusedGroup.group_id ? 'animate-spin' : ''
                        }`}
                      />
                      <span>微調整した範囲・中心角で再フィット</span>
                    </button>
                  </div>
                </>
              );
            })()}
          </div>
        </div>
      )}
    </div>
  );
};
