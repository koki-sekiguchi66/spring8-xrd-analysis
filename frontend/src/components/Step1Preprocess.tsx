import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FolderOpen,
  Play,
  Sparkles,
  CheckCircle2,
  Sliders,
  ArrowRight,
  RefreshCw,
  FileSpreadsheet,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { TutorialGuideBanner } from './TutorialGuideBanner';
import { apiGet, apiPost, fmtFixed } from '../lib/utils';
import type { PreprocessPreviewData, PreprocessRunResponse } from '../types/xrd';

export interface Step1PreprocessProps {
  folderPath: string;
  setFolderPath: (val: string) => void;
  specimenName: string;
  setSpecimenName: (val: string) => void;
  preprocessResult: PreprocessRunResponse | null;
  setPreprocessResult: (res: PreprocessRunResponse) => void;
  onProceedStep2: () => void;
}

export const Step1Preprocess: React.FC<Step1PreprocessProps> = ({
  folderPath,
  setFolderPath,
  specimenName,
  setSpecimenName,
  preprocessResult,
  setPreprocessResult,
  onProceedStep2,
}) => {
  const [sampleFolder, setSampleFolder] = useState<string>('');
  const [thMin, setThMin] = useState<number>(10.2);
  const [spikeFactor, setSpikeFactor] = useState<number>(5.0);
  const [valleyDistance, setValleyDistance] = useState<number>(100);
  const [valleyWindow, setValleyWindow] = useState<number>(11);
  const [forceRecompute, setForceRecompute] = useState<boolean>(false);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  const [loading, setLoading] = useState<boolean>(false);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedNum, setSelectedNum] = useState<number>(50);
  const [previewData, setPreviewData] = useState<PreprocessPreviewData | null>(
    preprocessResult?.preview ?? null
  );
  const [zoomBaseline, setZoomBaseline] = useState<boolean>(true);

  useEffect(() => {
    apiGet<{ sample_xrd_folder: string }>('/api/preprocess/sample-paths')
      .then((res) => {
        if (res.sample_xrd_folder) {
          setSampleFolder(res.sample_xrd_folder);
          if (!folderPath) {
            setFolderPath(res.sample_xrd_folder);
            setSpecimenName('Seki_age_2_tensile');
          }
        }
      })
      .catch(() => {
        // ignore
      });
  }, [folderPath, setFolderPath, setSpecimenName]);

  const inferSpecimenFromPath = (rawPath: string): string => {
    const parts = rawPath.split(/[\\/]/).filter(Boolean);
    if (parts.length === 0) return '';
    const last = parts[parts.length - 1];
    if (['tth', 'bcg_removed_arpls', 'others'].includes(last.toLowerCase()) && parts.length >= 2) {
      return parts[parts.length - 2];
    }
    return last;
  };

  const handleBrowseNative = async () => {
    try {
      const res = await apiPost<{ selected_path: string; cancelled: boolean }>(
        '/api/dialog/select',
        {
          mode: 'folder',
          title: '解析対象の試料ディレクトリ (.tth 格納フォルダ) を選択',
          initial_dir: folderPath || undefined,
        }
      );
      if (!res.cancelled && res.selected_path) {
        setFolderPath(res.selected_path);
        const inferred = inferSpecimenFromPath(res.selected_path);
        if (inferred) {
          setSpecimenName(inferred);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleRunPreprocess = async (overridePath?: string) => {
    const targetFolder = overridePath ?? folderPath;
    if (!targetFolder.trim()) {
      setError('解析対象のフォルダパスを入力または選択してください。');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<PreprocessRunResponse>('/api/preprocess/run', {
        folder_path: targetFolder.trim(),
        specimen_name: specimenName.trim() || undefined,
        th_min: thMin,
        spike_threshold_factor: spikeFactor,
        valley_distance: valleyDistance,
        valley_avg_window: valleyWindow,
        force_recompute: forceRecompute,
      });
      setPreprocessResult(res);
      setFolderPath(res.folder_path);
      setSpecimenName(res.specimen_name);
      setPreviewData(res.preview);
      setSelectedNum(res.preview.num);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleLoadPreviewNum = useCallback(
    async (numVal: number) => {
      if (!folderPath.trim()) return;
      setSelectedNum(numVal);
      setPreviewLoading(true);
      setError(null);
      try {
        const q = new URLSearchParams({
          folder_path: folderPath.trim(),
          th_min: String(thMin),
          spike_threshold_factor: String(spikeFactor),
          valley_distance: String(valleyDistance),
          valley_avg_window: String(valleyWindow),
        });
        const res = await apiGet<PreprocessPreviewData>(
          `/api/preprocess/preview/${numVal}?${q.toString()}`
        );
        setPreviewData(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setPreviewLoading(false);
      }
    },
    [folderPath, thMin, spikeFactor, valleyDistance, valleyWindow]
  );

  const plotTraces = useMemo(() => {
    if (!previewData) return [];
    return [
      {
        x: previewData.x,
        y: previewData.y_raw,
        type: 'scattergl',
        mode: 'lines',
        name: 'Raw Data (生波形)',
        line: { color: '#52525b', width: 1.2 },
        opacity: 0.55,
      },
      {
        x: previewData.x,
        y: previewData.y_despiked,
        type: 'scattergl',
        mode: 'lines',
        name: 'Despiked (スパイク除去)',
        line: { color: '#06b6d4', width: 1.5 },
        opacity: 0.8,
      },
      {
        x: previewData.monotonic_x,
        y: previewData.monotonic_y,
        type: 'scatter',
        mode: 'markers',
        name: 'Rubberband Anchors (下側包絡点)',
        marker: {
          color: '#f59e0b',
          size: 8,
          symbol: 'circle',
          line: { color: '#09090b', width: 1 },
        },
      },
      {
        x: previewData.x,
        y: previewData.y_background,
        type: 'scattergl',
        mode: 'lines',
        name: `Baseline (${previewData.method_used})`,
        line: { color: '#10b981', width: 2.5, dash: 'dash' },
      },
      {
        x: previewData.x,
        y: previewData.y_corrected,
        type: 'scattergl',
        mode: 'lines',
        name: 'BG Corrected (BG除去後波形)',
        line: { color: '#f43f5e', width: 2 },
      },
    ];
  }, [previewData]);

  const plotLayout = useMemo(() => {
    return {
      title: {
        text: previewData
          ? `バックグラウンド除去 検証プレビュー — ${previewData.filename} (num=#${previewData.num}, 補間法: ${previewData.method_used})`
          : 'バックグラウンド除去 プレビュー',
        font: { size: 15, color: '#f4f4f5' },
      },
      xaxis: {
        title: '回折角 2θ (deg.)',
      },
      yaxis: {
        title: '強度 Intensity (a.u.)',
        ...(zoomBaseline ? { range: [-120, 650] } : { autorange: true }),
      },
    };
  }, [previewData, zoomBaseline]);

  const availableNums = preprocessResult?.nums ?? [];

  return (
    <div className="space-y-6">
      {/* Beginner Tutorial Banner */}
      <TutorialGuideBanner
        mode="xrd"
        stepTitle="Step 1: フォルダ選択 ＆ 自動仕分け・バックグラウンド除去"
        summary="まずは測定データ（.tth ファイル）が入ったフォルダを選択し、ファイル仕分けとバックグラウンド（背景散乱）除去を一括実行します。"
        steps={[
          {
            badge: 'STEP 1',
            title: '解析する試料フォルダを選択',
            description:
              '「参照」ボタンで .tth ファイルが入ったフォルダを選ぶか、「SPring-8 実測サンプルデータをロード」をクリックします。',
          },
          {
            badge: 'STEP 2',
            title: '一括実行ボタンをクリック',
            description:
              '「.tth 自動仕分け ＆ 全ファイルBG除去を一括実行」を押すと、tth/ と others/ への仕分けと全ファイルのBG除去が自動で行われます。',
          },
          {
            badge: 'STEP 3',
            title: '右のグラフでBG除去波形を確認して Step 2 へ',
            description:
              '緑の破線（ベースライン）が波形の底に綺麗に沿っていることを確認し、「Step 2へ進む」をクリックします。',
          },
        ]}
        glossary={[
          {
            term: 'Rubberband（下側凸包）＋ PCHIP補間とは？',
            meaning:
              '回折プロファイルの極小谷（アンカー点）を下側からゴム紐を張るように結ぶことで、重畳ピークの裾野を削りすぎずに滑らかなバックグラウンド曲線を差し引く手法です。',
          },
          {
            term: 'スパイク除去 (Despiking) とは？',
            meaning:
              '検出器の1点ノイズ（異常な鋭い飛び値）を移動中央値との比較で自動検出し、周囲の平均値に置き換えて誤フィットを防ぎます。',
          },
        ]}
        tip="一度BG除去を実行したフォルダには bcg_removed_arpls/*.csv が保存されるため、2回目以降は数秒で高速に読み込まれます。"
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Configuration Column */}
        <section className="lg:col-span-5 panel-card p-6 space-y-5 flex flex-col">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
            <div>
              <span className="text-xs font-mono font-bold text-cyan-400 tracking-wider">
                STAGE 01 / PREPROCESS
              </span>
              <h2 className="text-xl font-bold text-zinc-100 mt-0.5">
                試料フォルダ選択 ＆ 一括前処理
              </h2>
            </div>
            <FolderOpen className="w-6 h-6 text-cyan-400 shrink-0" />
          </div>

          <div className="space-y-4" data-tour="step1-folder-select">
            <div>
              <label htmlFor="specimen-folder-input" className="label-sm block mb-2">
                解析対象ディレクトリパス (`.tth` ファイル格納フォルダ)
              </label>
              <div className="flex gap-2.5">
                <input
                  id="specimen-folder-input"
                  type="text"
                  value={folderPath}
                  onChange={(e) => {
                    const val = e.target.value;
                    setFolderPath(val);
                    const inferred = inferSpecimenFromPath(val);
                    if (inferred) {
                      setSpecimenName(inferred);
                    }
                  }}
                  placeholder="D:\Tsujilab\SP8\0.8C90CR"
                  className="input-field font-mono flex-1"
                />
                <button
                  type="button"
                  onClick={handleBrowseNative}
                  className="btn-secondary shrink-0"
                >
                  <FolderOpen className="w-4 h-4 text-cyan-400" />
                  <span>参照</span>
                </button>
              </div>
            </div>

            {sampleFolder && (
              <button
                type="button"
                onClick={() => {
                  setFolderPath(sampleFolder);
                  setSpecimenName('Seki_age_2_tensile');
                  handleRunPreprocess(sampleFolder);
                }}
                className="w-full py-2.5 px-4 bg-cyan-950/50 hover:bg-cyan-900/50 border border-cyan-500/40 rounded-xl text-sm font-medium text-cyan-200 flex items-center justify-center gap-2 transition-colors"
              >
                <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>SPring-8 実測サンプルデータ (`Seki_age_2_tensile`) をロードして実行</span>
              </button>
            )}

            <div>
              <label htmlFor="specimen-name-input" className="label-sm block mb-2">
                試料名 (`_initial.xlsx` / `output.xlsx` のファイル名接頭辞)
              </label>
              <input
                id="specimen-name-input"
                type="text"
                value={specimenName}
                onChange={(e) => setSpecimenName(e.target.value)}
                placeholder="0.8C90CR"
                className="input-field font-mono"
              />
            </div>
          </div>

          {/* Collapsible Advanced BG Removal Parameters */}
          <div data-tour="step1-advanced-params" className="rounded-xl bg-zinc-950/80 border border-zinc-800/90 overflow-hidden">
            <button
              type="button"
              onClick={() => setShowAdvanced((prev) => !prev)}
              className="w-full px-4 py-3 flex items-center justify-between text-sm font-semibold text-zinc-200 hover:bg-zinc-900/60 transition-colors"
            >
              <span className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-amber-400" />
                <span>バックグラウンド除去 詳細パラメータ設定（通常は初期値でOK）</span>
              </span>
              {showAdvanced ? (
                <ChevronUp className="w-4 h-4 text-zinc-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-zinc-400" />
              )}
            </button>

            {showAdvanced && (
              <div className="p-4 pt-2 border-t border-zinc-800 space-y-4">
                <div className="grid grid-cols-2 gap-3.5">
                  <div>
                    <label htmlFor="th-min-input" className="block text-xs text-zinc-300 mb-1">
                      最小回折角 `th_min` (°)
                    </label>
                    <input
                      id="th-min-input"
                      type="number"
                      step="0.1"
                      value={thMin}
                      onChange={(e) => setThMin(Number(e.target.value))}
                      className="input-field py-2 font-mono tabular-nums"
                    />
                  </div>
                  <div>
                    <label htmlFor="spike-factor-input" className="block text-xs text-zinc-300 mb-1">
                      スパイク除去係数 (`threshold`)
                    </label>
                    <input
                      id="spike-factor-input"
                      type="number"
                      step="0.5"
                      value={spikeFactor}
                      onChange={(e) => setSpikeFactor(Number(e.target.value))}
                      className="input-field py-2 font-mono tabular-nums"
                    />
                  </div>
                  <div>
                    <label htmlFor="valley-dist-input" className="block text-xs text-zinc-300 mb-1">
                      極小谷探索間隔 (`distance`)
                    </label>
                    <input
                      id="valley-dist-input"
                      type="number"
                      step="10"
                      value={valleyDistance}
                      onChange={(e) => setValleyDistance(Number(e.target.value))}
                      className="input-field py-2 font-mono tabular-nums"
                    />
                  </div>
                  <div>
                    <label htmlFor="valley-win-input" className="block text-xs text-zinc-300 mb-1">
                      アンカー平均窓幅 (`window`)
                    </label>
                    <input
                      id="valley-win-input"
                      type="number"
                      step="2"
                      value={valleyWindow}
                      onChange={(e) => setValleyWindow(Number(e.target.value))}
                      className="input-field py-2 font-mono tabular-nums"
                    />
                  </div>
                </div>

                <label className="flex items-center gap-2.5 text-sm text-zinc-200 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={forceRecompute}
                    onChange={(e) => setForceRecompute(e.target.checked)}
                    className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-cyan-500"
                  />
                  <span>既存の `bcg_removed_arpls/*.csv` を強制的に再計算する</span>
                </label>
              </div>
            )}
          </div>

          {error && (
            <div
              role="alert"
              className="p-4 rounded-xl bg-rose-950/60 border border-rose-500/40 text-sm text-rose-200 flex items-start gap-2.5"
            >
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="button"
            data-tour="step1-run-btn"
            disabled={loading}
            onClick={() => handleRunPreprocess()}
            className="btn-primary w-full py-3.5 text-base"
          >
            {loading ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                <span>ファイル仕分け・全ファイルBG除去を実行中...</span>
              </>
            ) : (
              <>
                <Play className="w-5 h-5 fill-current" />
                <span>`.tth` 自動仕分け ＆ 全ファイルBG除去を一括実行</span>
              </>
            )}
          </button>

          {preprocessResult && (
            <div className="bg-zinc-950 border border-emerald-500/40 rounded-xl p-4 space-y-3.5">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-emerald-400 flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5" />
                  前処理完了 (
                  {preprocessResult.separation.already_separated
                    ? '仕分け済・高速ロード'
                    : '新規仕分け完了'}
                  )
                </span>
                <span className="text-sm font-mono tabular-nums font-bold text-zinc-200">
                  全 {preprocessResult.nums.length} ファイル
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2.5 text-center bg-zinc-900/90 rounded-lg p-3 border border-zinc-800">
                <div>
                  <div className="text-xs text-zinc-400">`.tth` 総数</div>
                  <div className="text-base font-mono tabular-nums font-bold text-cyan-400 mt-0.5">
                    {preprocessResult.separation.total_tth_count}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-400">開始〜終了 num</div>
                  <div className="text-base font-mono tabular-nums font-bold text-zinc-100 mt-0.5">
                    {preprocessResult.nums[0]}–
                    {preprocessResult.nums[preprocessResult.nums.length - 1]}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-zinc-400">補間アルゴリズム</div>
                  <div className="text-base font-mono tabular-nums font-bold text-emerald-400 mt-0.5">
                    {previewData?.method_used ?? 'PCHIP'}
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={onProceedStep2}
                className="btn-emerald w-full py-3 text-base"
              >
                <span>Step 2: 初期値マルチファイル探索・相ペア選択へ進む</span>
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          )}
        </section>

        {/* Right Interactive Waveform Inspection Column */}
        <section data-tour="step1-preview-plot" className="lg:col-span-7 panel-card p-6 space-y-4 flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4">
            <div>
              <span className="text-xs font-mono font-bold text-amber-400 tracking-wider">
                BASELINE &amp; SPIKE DIAGNOSTICS
              </span>
              <h3 className="text-lg font-bold text-zinc-100 mt-0.5">
                生波形 / スパイク除去 / Rubberbandアンカー / PCHIPベースライン 検証グラフ
              </h3>
            </div>

            <label className="flex items-center gap-2 text-sm text-zinc-200 cursor-pointer select-none bg-zinc-950 px-3.5 py-2 rounded-lg border border-zinc-800">
              <input
                type="checkbox"
                checked={zoomBaseline}
                onChange={(e) => setZoomBaseline(e.target.checked)}
                className="w-4 h-4 rounded border-zinc-700 bg-zinc-900 text-cyan-500"
              />
              <span>ベースライン付近を拡大 (-120〜650 a.u.)</span>
            </label>
          </div>

          {/* File Number Selector Bar */}
          {availableNums.length > 0 && (
            <div className="flex flex-wrap items-center gap-3 bg-zinc-950 border border-zinc-800 rounded-xl p-3.5">
              <label
                htmlFor="preview-num-slider"
                className="text-sm font-semibold text-zinc-200 shrink-0"
              >
                確認ファイル番号 `num`:
              </label>
              <input
                id="preview-num-slider"
                type="range"
                min={availableNums[0]}
                max={availableNums[availableNums.length - 1]}
                value={selectedNum}
                onChange={(e) => setSelectedNum(Number(e.target.value))}
                onMouseUp={() => handleLoadPreviewNum(selectedNum)}
                onKeyUp={() => handleLoadPreviewNum(selectedNum)}
                className="flex-1 accent-cyan-400"
              />
              <span className="px-3 py-1 rounded-lg bg-zinc-900 border border-zinc-700 text-sm font-mono tabular-nums text-cyan-300 font-bold min-w-[5rem] text-center">
                #{selectedNum}
              </span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {[5, 50, 300, 500, 900, 1050]
                  .filter((n) => availableNums.includes(n))
                  .map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => handleLoadPreviewNum(n)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-mono tabular-nums border transition-colors ${
                        selectedNum === n
                          ? 'bg-cyan-500/25 border-cyan-400 text-cyan-200 font-bold'
                          : 'bg-zinc-900 border-zinc-800 text-zinc-300 hover:text-white'
                      }`}
                    >
                      #{n}
                    </button>
                  ))}
              </div>
            </div>
          )}

          {/* Main Plotly Overlay */}
          <div className="relative flex-1 min-h-[450px] bg-zinc-950 border border-zinc-800/80 rounded-xl p-2">
            {previewLoading && (
              <div className="absolute inset-0 z-10 bg-zinc-950/75 flex items-center justify-center text-base font-mono text-cyan-300">
                波形データ #{selectedNum} を読込中...
              </div>
            )}
            {previewData ? (
              <PlotlyChart data={plotTraces} layout={plotLayout} className="w-full h-[450px]" />
            ) : (
              <div className="h-[450px] flex flex-col items-center justify-center text-center p-8 text-zinc-400 space-y-4">
                <FileSpreadsheet className="w-12 h-12 text-zinc-600" />
                <p className="text-base text-zinc-200 font-semibold max-w-md">
                  左パネルから試料ディレクトリを選択し、「.tth 自動仕分け ＆ 全ファイルBG除去を一括実行」をクリックしてください。
                </p>
                {sampleFolder && (
                  <button
                    type="button"
                    onClick={() => {
                      setFolderPath(sampleFolder);
                      setSpecimenName('Seki_age_2_tensile');
                      handleRunPreprocess(sampleFolder);
                    }}
                    className="btn-primary"
                  >
                    <Sparkles className="w-4 h-4" />
                    <span>サンプルデータ (`Seki_age_2_tensile`) で今すぐ検証する</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};
