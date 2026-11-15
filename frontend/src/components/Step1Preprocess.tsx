import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FolderOpen,
  Play,
  ArrowRight,
  RefreshCw,
  FileSpreadsheet,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { Button } from './ui/Button';
import { EmptyCanvas } from './ui/EmptyCanvas';
import { Panel, PanelBody, PanelHeader } from './ui/Panel';
import { FieldLabel, TextInput, UnitNumberInput, CheckboxRow } from './ui/Field';
import { Disclosure } from './ui/Disclosure';
import { PlotFrame } from './ui/PlotFrame';
import { Notice } from './ui/Notice';
import { StatusBadge } from './ui/StatusBadge';
import { apiGet, apiPost } from '../lib/utils';
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
      setError('解析対象のフォルダパスを指定してください。');
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
        name: 'Raw',
        line: { color: '#52525b', width: 1.2 },
        opacity: 0.55,
      },
      {
        x: previewData.x,
        y: previewData.y_despiked,
        type: 'scattergl',
        mode: 'lines',
        name: 'Despiked',
        line: { color: '#38bdf8', width: 1.5 },
        opacity: 0.85,
      },
      {
        x: previewData.monotonic_x,
        y: previewData.monotonic_y,
        type: 'scatter',
        mode: 'markers',
        name: 'Anchors',
        marker: {
          color: '#f59e0b',
          size: 7,
          symbol: 'circle',
          line: { color: '#0a0b0e', width: 1 },
        },
      },
      {
        x: previewData.x,
        y: previewData.y_background,
        type: 'scattergl',
        mode: 'lines',
        name: `Baseline (${previewData.method_used})`,
        line: { color: '#10b981', width: 2, dash: 'dash' },
      },
      {
        x: previewData.x,
        y: previewData.y_corrected,
        type: 'scattergl',
        mode: 'lines',
        name: 'BG Corrected',
        line: { color: '#f43f5e', width: 2 },
      },
    ];
  }, [previewData]);

  const plotLayout = useMemo(() => {
    return {
      margin: { l: 56, r: 16, t: 16, b: 44 },
      xaxis: {
        title: '2θ (deg)',
      },
      yaxis: {
        title: 'Intensity (a.u.)',
        ...(zoomBaseline ? { range: [-120, 650] } : { autorange: true }),
      },
    };
  }, [zoomBaseline]);

  const availableNums = preprocessResult?.nums ?? [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
      {/* Left Inspector Column */}
      <Panel className="lg:col-span-4">
        <PanelHeader
          title="前処理"
          actions={
            preprocessResult ? (
              <StatusBadge tone="emerald" dot>
                完了
              </StatusBadge>
            ) : undefined
          }
        />
        <PanelBody className="space-y-3.5">
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <label htmlFor="specimen-folder-input" className="text-[11px] font-medium text-[#858d9c]">
                  フォルダ
                </label>
                {sampleFolder && (
                  <button
                    type="button"
                    onClick={() => {
                      setFolderPath(sampleFolder);
                      setSpecimenName('Seki_age_2_tensile');
                      handleRunPreprocess(sampleFolder);
                    }}
                    className="text-[11px] font-medium text-sky-400 hover:text-sky-300 transition-colors"
                  >
                    サンプル読込
                  </button>
                )}
              </div>
              <div className="flex gap-1.5">
                <TextInput
                  id="specimen-folder-input"
                  mono
                  value={folderPath}
                  onChange={(e) => {
                    const val = e.target.value;
                    setFolderPath(val);
                    const inferred = inferSpecimenFromPath(val);
                    if (inferred) setSpecimenName(inferred);
                  }}
                  placeholder="D:\Data\Specimen"
                  className="flex-1"
                />
                <Button variant="secondary" size="sm" onClick={handleBrowseNative}>
                  <FolderOpen className="size-3.5 text-sky-400" aria-hidden="true" />
                  <span>選択</span>
                </Button>
              </div>
            </div>

            <div>
              <FieldLabel htmlFor="specimen-name-input">
                試料名
              </FieldLabel>
              <TextInput
                id="specimen-name-input"
                mono
                value={specimenName}
                onChange={(e) => setSpecimenName(e.target.value)}
                placeholder="Seki_age_2_tensile"
              />
            </div>
          </div>

          <Disclosure
            title="詳細パラメータ"
            summary={`th_min ${thMin}°`}
            open={showAdvanced}
            onToggle={() => setShowAdvanced((prev) => !prev)}
          >
            <div className="space-y-2.5">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <FieldLabel htmlFor="th-min-input">th_min</FieldLabel>
                  <UnitNumberInput
                    id="th-min-input"
                    step="0.1"
                    unit="deg"
                    value={thMin}
                    onChange={(e) => setThMin(Number(e.target.value))}
                  />
                </div>
                <div>
                  <FieldLabel htmlFor="spike-factor-input">スパイク閾値</FieldLabel>
                  <UnitNumberInput
                    id="spike-factor-input"
                    step="0.5"
                    unit="x"
                    value={spikeFactor}
                    onChange={(e) => setSpikeFactor(Number(e.target.value))}
                  />
                </div>
                <div>
                  <FieldLabel htmlFor="valley-dist-input">谷探索間隔</FieldLabel>
                  <UnitNumberInput
                    id="valley-dist-input"
                    step="10"
                    unit="pts"
                    value={valleyDistance}
                    onChange={(e) => setValleyDistance(Number(e.target.value))}
                  />
                </div>
                <div>
                  <FieldLabel htmlFor="valley-win-input">平均窓幅</FieldLabel>
                  <UnitNumberInput
                    id="valley-win-input"
                    step="2"
                    unit="pts"
                    value={valleyWindow}
                    onChange={(e) => setValleyWindow(Number(e.target.value))}
                  />
                </div>
              </div>

              <CheckboxRow
                checked={forceRecompute}
                onChange={setForceRecompute}
                label="キャッシュ再計算"
              />
            </div>
          </Disclosure>

          {error && <Notice tone="error">{error}</Notice>}

          <Button
            variant="primary"
            block
            disabled={loading}
            onClick={() => handleRunPreprocess()}
          >
            {loading ? (
              <>
                <RefreshCw className="size-3.5 animate-spin" aria-hidden="true" />
                <span>処理中...</span>
              </>
            ) : (
              <>
                <Play className="size-3 fill-current" aria-hidden="true" />
                <span>実行</span>
              </>
            )}
          </Button>

          {preprocessResult && (
            <div className="pt-3 border-t border-[#22262f] space-y-2.5">
              <div className="grid grid-cols-3 divide-x divide-[#22262f] rounded-md bg-[#08090c] border border-[#22262f] text-center">
                <div className="py-1.5 px-2">
                  <div className="text-[10px] text-[#5d6473]">.tth</div>
                  <div className="text-[13px] font-mono tabular-nums font-semibold text-sky-300 mt-0.5">
                    {preprocessResult.separation.total_tth_count}
                  </div>
                </div>
                <div className="py-1.5 px-2">
                  <div className="text-[10px] text-[#5d6473]">範囲</div>
                  <div className="text-[13px] font-mono tabular-nums font-semibold text-[#eef0f4] mt-0.5">
                    {preprocessResult.nums[0]}–{preprocessResult.nums[preprocessResult.nums.length - 1]}
                  </div>
                </div>
                <div className="py-1.5 px-2">
                  <div className="text-[10px] text-[#5d6473]">補間</div>
                  <div className="text-[13px] font-mono font-semibold text-emerald-300 mt-0.5 truncate">
                    {previewData?.method_used ?? 'PCHIP'}
                  </div>
                </div>
              </div>

              <Button variant="emerald" block onClick={onProceedStep2}>
                <span>次へ: 初期値</span>
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </Button>
            </div>
          )}
        </PanelBody>
      </Panel>

      {/* Right Preview Plot Column */}
      <PlotFrame
        className="lg:col-span-8"
        title="ベースライン除去"
        subtitle={
          previewData
            ? `${previewData.filename} #${previewData.num} ${previewData.method_used}`
            : undefined
        }
        toolbar={
          <CheckboxRow
            checked={zoomBaseline}
            onChange={setZoomBaseline}
            label="低強度域拡大"
          />
        }
        subbar={
          availableNums.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2.5">
              <label
                htmlFor="preview-num-slider"
                className="text-[11px] font-medium text-[#858d9c] shrink-0"
              >
                フレーム
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
                className="flex-1 min-w-[140px] accent-sky-400"
              />
              <span className="px-2 py-0.5 rounded bg-[#08090c] border border-[#22262f] text-[11px] font-mono tabular-nums text-sky-300 min-w-[3.5rem] text-center">
                #{selectedNum}
              </span>
              <div className="flex items-center gap-1 flex-wrap">
                {[5, 50, 300, 500, 900, 1050]
                  .filter((n) => availableNums.includes(n))
                  .map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => handleLoadPreviewNum(n)}
                      className={`h-6 px-2 rounded text-[11px] font-mono tabular-nums border transition-colors ${
                        selectedNum === n
                          ? 'bg-sky-500/15 border-sky-500/50 text-sky-300 font-semibold'
                          : 'bg-[#08090c] border-[#22262f] text-[#858d9c] hover:text-[#eef0f4]'
                      }`}
                    >
                      #{n}
                    </button>
                  ))}
              </div>
            </div>
          ) : undefined
        }
      >
        <div className="relative min-h-[480px]">
          {previewLoading && (
            <div className="absolute inset-0 z-10 bg-[#08090c]/80 flex items-center justify-center text-[11px] font-mono text-sky-300">
              Loading #{selectedNum}...
            </div>
          )}
          {previewData ? (
            <PlotlyChart data={plotTraces} layout={plotLayout} className="w-full h-[500px]" />
          ) : (
            <EmptyCanvas
              className="h-[500px]"
              label="データ未読込"
              actionLabel={sampleFolder ? 'サンプル読込' : undefined}
              actionIcon={<Play className="size-3 fill-current text-sky-400" />}
              onAction={
                sampleFolder
                  ? () => {
                      setFolderPath(sampleFolder);
                      setSpecimenName('Seki_age_2_tensile');
                      handleRunPreprocess(sampleFolder);
                    }
                  : undefined
              }
            />
          )}
        </div>
      </PlotFrame>
    </div>
  );
};
