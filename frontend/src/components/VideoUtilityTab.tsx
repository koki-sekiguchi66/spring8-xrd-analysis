import React, { useCallback, useEffect, useState } from 'react';
import {
  FolderOpen,
  Play,
  RefreshCw,
  FileVideo,
} from 'lucide-react';
import { Button } from './ui/Button';
import { Panel, PanelBody, PanelHeader } from './ui/Panel';
import { SegmentedControl } from './ui/SegmentedControl';
import { MetricCell, MetricStrip } from './ui/MetricStrip';
import { FieldLabel, SelectInput, TextInput, UnitNumberInput } from './ui/Field';
import { StatusBadge } from './ui/StatusBadge';
import { Notice } from './ui/Notice';
import { apiGet, apiPost, fmtFixed, runVideoExportStream } from '../lib/utils';
import type { VideoInspectResponse } from '../types/xrd';

interface SamplePathsResponse {
  sample_xrd_folder: string;
  sample_dic_folder: string;
  sample_dic_video: string;
}

interface ExportCompleteSummary {
  mode: string;
  saved_count?: number;
  total_saved_frames?: number;
  video_count?: number;
  output_dir?: string;
  output_root_dir?: string;
  sample_files?: string[];
}

export const VideoUtilityTab: React.FC = () => {
  const [mode, setMode] = useState<'single' | 'folder'>('single');
  const [targetPath, setTargetPath] = useState<string>('');
  const [samplePaths, setSamplePaths] = useState<SamplePathsResponse | null>(null);

  const [startSec, setStartSec] = useState<number>(0.0);
  const [stopSec, setStopSec] = useState<number>(600.0);
  const [stepSec, setStepSec] = useState<number>(1.0);
  const [ext, setExt] = useState<'jpg' | 'png'>('jpg');
  const [outputDir, setOutputDir] = useState<string>('');
  const [basename, setBasename] = useState<string>('');

  const [inspectData, setInspectData] = useState<VideoInspectResponse | null>(null);
  const [loadingInspect, setLoadingInspect] = useState<boolean>(false);
  const [runningExport, setRunningExport] = useState<boolean>(false);
  const [progressPct, setProgressPct] = useState<number>(0);
  const [progressDetail, setProgressDetail] = useState<string>('');
  const [currentCount, setCurrentCount] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [exportResult, setExportResult] = useState<ExportCompleteSummary | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    apiGet<SamplePathsResponse>('/api/preprocess/sample-paths')
      .then((res) => {
        setSamplePaths(res);
        if (!targetPath && res.sample_dic_video) {
          setTargetPath(res.sample_dic_video);
        }
      })
      .catch(() => {
        // ignore
      });
  }, []);

  const handleInspect = useCallback(
    async (
      overridePath?: string,
      overrideMode?: 'single' | 'folder',
      autoSetStop = false
    ) => {
      const pathToUse = (overridePath ?? targetPath).trim();
      const modeToUse = overrideMode ?? mode;
      if (!pathToUse) return;

      setLoadingInspect(true);
      setErrorMsg(null);
      try {
        const res = await apiPost<VideoInspectResponse>('/api/video/inspect', {
          mode: modeToUse,
          target_path: pathToUse,
          start_sec: startSec,
          stop_sec: autoSetStop ? null : stopSec,
          step_sec: stepSec,
        });
        setInspectData(res);
        setStopSec(res.recommended_stop_sec > 0 ? res.recommended_stop_sec : 600.0);
        setOutputDir(res.default_output_dir);
        setBasename(res.default_basename);
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        setLoadingInspect(false);
      }
    },
    [targetPath, mode, startSec, stopSec, stepSec]
  );

  useEffect(() => {
    if (targetPath && !inspectData && !loadingInspect) {
      handleInspect(targetPath, mode, true);
    }
  }, [targetPath]);

  const handleSelectMode = (newMode: 'single' | 'folder') => {
    setMode(newMode);
    setExportResult(null);
    if (samplePaths) {
      const nextTarget =
        newMode === 'single' ? samplePaths.sample_dic_video : samplePaths.sample_dic_folder;
      if (nextTarget) {
        setTargetPath(nextTarget);
        setOutputDir('');
        handleInspect(nextTarget, newMode, true);
      }
    }
  };

  const handleBrowseTarget = async () => {
    setErrorMsg(null);
    try {
      const dialogMode = mode === 'single' ? 'video_file' : 'folder';
      const title =
        mode === 'single'
          ? 'DICフレーム切り出し対象の動画ファイルを選択'
          : 'DICフレーム一括切り出し対象の動画フォルダを選択';
      const res = await apiPost<{ selected_path: string; cancelled: boolean }>(
        '/api/dialog/select',
        {
          mode: dialogMode,
          title,
          initial_dir: targetPath || undefined,
        }
      );
      if (!res.cancelled && res.selected_path) {
        setTargetPath(res.selected_path);
        setOutputDir('');
        await handleInspect(res.selected_path, mode, true);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  };

  const handleBrowseOutputDir = async () => {
    try {
      const res = await apiPost<{ selected_path: string; cancelled: boolean }>(
        '/api/dialog/select',
        {
          mode: 'save_folder',
          title: 'フレーム画像の出力先フォルダを選択',
          initial_dir: outputDir || targetPath || undefined,
        }
      );
      if (!res.cancelled && res.selected_path) {
        setOutputDir(res.selected_path);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  };

  const handleRunExport = async () => {
    if (!targetPath.trim()) {
      setErrorMsg('対象の動画ファイルまたはフォルダを指定してください。');
      return;
    }
    setRunningExport(true);
    setErrorMsg(null);
    setExportResult(null);
    setProgressPct(0);
    setProgressDetail('初期化中...');

    const payload = {
      mode,
      target_path: targetPath.trim(),
      start_sec: Number(startSec),
      stop_sec: Number(stopSec),
      step_sec: Number(stepSec),
      output_dir: outputDir.trim() || null,
      basename: basename.trim() || null,
      ext,
    };

    try {
      await runVideoExportStream(payload, (rawMsg) => {
        const msg = rawMsg as Record<string, unknown>;
        if (msg.type === 'progress') {
          setProgressPct(Number(msg.progress_pct ?? 0));
          setCurrentCount(Number(msg.current ?? 0));
          setTotalCount(Number(msg.total ?? 0));
          setProgressDetail(
            `${msg.video_name || ''} — ${msg.current}/${msg.total}`
          );
        } else if (msg.type === 'complete') {
          setProgressPct(100);
          setExportResult(msg as unknown as ExportCompleteSummary);
        } else if (msg.type === 'error') {
          setErrorMsg(String(msg.detail || '動画切り出し中にエラーが発生しました'));
        }
      });
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setRunningExport(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
      {/* Left Extraction Controls */}
      <Panel className="lg:col-span-5">
        <PanelHeader title="DIC フレーム抽出" />
        <PanelBody className="space-y-4">
          <div>
            <FieldLabel>入力モード</FieldLabel>
            <SegmentedControl
              fullWidth
              ariaLabel="入力モード"
              value={mode}
              onChange={handleSelectMode}
              options={[
                {
                  value: 'single',
                  label: '単一動画',
                  icon: <FileVideo className="size-3.5" aria-hidden="true" />,
                  accent: 'amber',
                },
                {
                  value: 'folder',
                  label: 'フォルダ一括',
                  icon: <FolderOpen className="size-3.5" aria-hidden="true" />,
                  accent: 'amber',
                },
              ]}
            />
          </div>

          <div>
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <label htmlFor="dic-target-path" className="text-xs font-medium text-[#9ca3b0]">
                {mode === 'single' ? '動画ファイル' : '動画フォルダ'}
              </label>
              {samplePaths && (
                <button
                  type="button"
                  onClick={() => {
                    const p =
                      mode === 'single'
                        ? samplePaths.sample_dic_video
                        : samplePaths.sample_dic_folder;
                    setTargetPath(p);
                    handleInspect(p, mode, true);
                  }}
                  className="text-xs font-medium text-sky-400 hover:text-sky-300 transition-colors"
                >
                  サンプル読込
                </button>
              )}
            </div>
            <div className="flex gap-1.5">
              <TextInput
                id="dic-target-path"
                mono
                value={targetPath}
                onChange={(e) => setTargetPath(e.target.value)}
                placeholder={
                  mode === 'single'
                    ? 'C:\\path\\to\\video.mp4'
                    : 'C:\\path\\to\\video_folder'
                }
                className="flex-1"
              />
              <Button variant="secondary" size="sm" onClick={handleBrowseTarget}>
                <FolderOpen className="size-3.5 text-amber-400" aria-hidden="true" />
                <span>参照</span>
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleInspect(targetPath, mode, false)}
                disabled={loadingInspect || !targetPath.trim()}
                aria-label="メタデータ再取得"
                className="px-2"
              >
                <RefreshCw
                  className={`size-3.5 ${loadingInspect ? 'animate-spin' : ''}`}
                  aria-hidden="true"
                />
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <FieldLabel htmlFor="dic-start-sec">開始</FieldLabel>
              <UnitNumberInput
                id="dic-start-sec"
                step="0.1"
                min="0"
                unit="s"
                value={startSec}
                onChange={(e) => setStartSec(Math.max(0, parseFloat(e.target.value) || 0))}
                onBlur={() => handleInspect(targetPath, mode, false)}
              />
            </div>
            <div>
              <FieldLabel htmlFor="dic-stop-sec">終了</FieldLabel>
              <UnitNumberInput
                id="dic-stop-sec"
                step="0.5"
                min="0.1"
                unit="s"
                value={stopSec}
                onChange={(e) => setStopSec(Math.max(0.1, parseFloat(e.target.value) || 1.0))}
                onBlur={() => handleInspect(targetPath, mode, false)}
              />
            </div>
            <div>
              <FieldLabel htmlFor="dic-step-sec">間隔</FieldLabel>
              <UnitNumberInput
                id="dic-step-sec"
                step="0.1"
                min="0.02"
                unit="s"
                value={stepSec}
                onChange={(e) => setStepSec(Math.max(0.02, parseFloat(e.target.value) || 1.0))}
                onBlur={() => handleInspect(targetPath, mode, false)}
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <FieldLabel htmlFor="dic-ext">画像形式</FieldLabel>
              <SelectInput
                id="dic-ext"
                mono
                value={ext}
                onChange={(e) => setExt(e.target.value as 'jpg' | 'png')}
              >
                <option value="jpg">JPEG</option>
                <option value="png">PNG</option>
              </SelectInput>
            </div>
            <div className="col-span-2">
              <FieldLabel htmlFor="dic-basename">
                {mode === 'single' ? 'ファイル接頭辞' : 'サフィックス'}
              </FieldLabel>
              <TextInput
                id="dic-basename"
                mono
                value={basename}
                onChange={(e) => setBasename(e.target.value)}
                placeholder={mode === 'single' ? 'video_img' : '_img'}
              />
            </div>
          </div>

          <div>
            <FieldLabel htmlFor="dic-output-dir" hint="空欄で自動">
              出力先フォルダ
            </FieldLabel>
            <div className="flex gap-1.5">
              <TextInput
                id="dic-output-dir"
                mono
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                placeholder="動画と同階層"
                className="flex-1"
              />
              <Button
                variant="secondary"
                size="sm"
                onClick={handleBrowseOutputDir}
                aria-label="出力先を選択"
                className="px-2.5"
              >
                <FolderOpen className="size-3.5" aria-hidden="true" />
              </Button>
            </div>
          </div>

          <Button
            variant="amber"
            block
            onClick={handleRunExport}
            disabled={runningExport || !targetPath.trim()}
          >
            {runningExport ? (
              <>
                <RefreshCw className="size-4 animate-spin" aria-hidden="true" />
                <span className="tabular-nums">抽出中... {fmtFixed(progressPct, 1)}%</span>
              </>
            ) : (
              <>
                <Play className="size-3.5 fill-current" aria-hidden="true" />
                <span>フレーム抽出を実行</span>
              </>
            )}
          </Button>

          {errorMsg && <Notice tone="error">{errorMsg}</Notice>}
        </PanelBody>
      </Panel>

      {/* Right Telemetry, Table & Progress */}
      <div className="lg:col-span-7 space-y-4">
        <MetricStrip columns={4}>
          <MetricCell
            label="認識動画"
            value={inspectData ? inspectData.video_count : 0}
            unit="files"
          />
          <MetricCell
            label="総再生時間"
            value={inspectData ? fmtFixed(inspectData.total_duration_sec, 2) : '0.00'}
            unit="s"
          />
          <MetricCell
            label="フレームレート"
            value={
              inspectData && inspectData.videos[0]
                ? fmtFixed(inspectData.videos[0].fps, 2)
                : '0.00'
            }
            unit="fps"
          />
          <MetricCell
            label="出力予定"
            value={inspectData ? inspectData.expected_total_frames : 0}
            unit="frames"
            tone="amber"
          />
        </MetricStrip>

        <Panel>
          <PanelHeader
            title="動画メタデータ"
            subtitle={`間隔 ${fmtFixed(stepSec, 2)}s (${fmtFixed(startSec, 1)}–${fmtFixed(stopSec, 1)}s)`}
          />
          <div className="overflow-x-auto max-h-64">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="bg-[#121418] border-b border-[#23262e] text-xs text-[#9ca3b0]">
                  <th className="py-2 px-3 font-medium">ファイル名</th>
                  <th className="py-2 px-3 font-medium">形式</th>
                  <th className="py-2 px-3 font-medium text-right">解像度</th>
                  <th className="py-2 px-3 font-medium text-right">FPS</th>
                  <th className="py-2 px-3 font-medium text-right">フレーム</th>
                  <th className="py-2 px-3 font-medium text-right">時間</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2129] font-mono tabular-nums text-xs">
                {inspectData && inspectData.videos.length > 0 ? (
                  inspectData.videos.map((v) => (
                    <tr key={v.video_path} className="hover:bg-[#1c1f26]">
                      <td className="py-2 px-3 text-[#eceef2] font-sans font-medium">
                        {v.filename}
                      </td>
                      <td className="py-2 px-3">
                        <StatusBadge tone="sky" mono>
                          {v.extension}
                        </StatusBadge>
                      </td>
                      <td className="py-2 px-3 text-right text-[#9ca3b0]">
                        {v.width}×{v.height}
                      </td>
                      <td className="py-2 px-3 text-right text-[#9ca3b0]">
                        {fmtFixed(v.fps, 2)}
                      </td>
                      <td className="py-2 px-3 text-right text-[#eceef2]">{v.frame_count}</td>
                      <td className="py-2 px-3 text-right text-amber-300 font-semibold">
                        {fmtFixed(v.duration_sec, 2)} s
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[#636b78] font-sans">
                      動画を選択するとメタデータが表示されます
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            title="抽出進捗"
            actions={
              <span className="text-xs font-mono tabular-nums text-amber-300 font-semibold">
                {fmtFixed(progressPct, 1)}% ({currentCount}/
                {totalCount || (inspectData?.expected_total_frames ?? 0)})
              </span>
            }
          />
          <PanelBody className="space-y-3">
            <div className="w-full h-1.5 bg-[#0a0b0e] rounded-full overflow-hidden border border-[#23262e]">
              <div
                className="h-full bg-amber-400 origin-left transition-transform duration-150 ease-out"
                style={{
                  transform: `scaleX(${Math.min(1, Math.max(0, progressPct / 100))})`,
                }}
              />
            </div>

            {progressDetail && (
              <div className="text-xs font-mono tabular-nums text-[#9ca3b0] truncate">
                {progressDetail}
              </div>
            )}

            {exportResult && (
              <Notice tone="success">
                <div className="font-medium">
                  出力完了 —{' '}
                  <span className="font-mono tabular-nums">
                    {exportResult.saved_count ?? exportResult.total_saved_frames ?? 0}
                  </span>{' '}
                  枚保存
                </div>
                <div className="text-xs font-mono text-emerald-300/80 break-all mt-0.5">
                  {exportResult.output_dir || exportResult.output_root_dir}
                </div>
              </Notice>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
};
