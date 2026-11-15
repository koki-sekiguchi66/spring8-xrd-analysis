import React, { useCallback, useEffect, useState } from 'react';
import {
  Film,
  FolderOpen,
  Play,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Clock,
  Layers,
  Image as ImageIcon,
  Sparkles,
  FileVideo,
} from 'lucide-react';
import { TutorialGuideBanner } from './TutorialGuideBanner';
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
    [targetPath, mode, startSec, stopSec, stepSec, outputDir]
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
    setProgressDetail('動画ストリームを初期化中...');

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
        const msg = rawMsg as Record<string, any>;
        if (msg.type === 'progress') {
          setProgressPct(msg.progress_pct ?? 0);
          setCurrentCount(msg.current ?? 0);
          setTotalCount(msg.total ?? 0);
          setProgressDetail(
            `${msg.video_name || ''} — ${msg.current}/${msg.total} フレーム完了`
          );
        } else if (msg.type === 'complete') {
          setProgressPct(100);
          setExportResult(msg as ExportCompleteSummary);
        } else if (msg.type === 'error') {
          setErrorMsg(msg.detail || '動画切り出し中にエラーが発生しました');
        }
      });
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setRunningExport(false);
    }
  };

  return (
    <div className="space-y-6">
      <TutorialGuideBanner
        mode="dic"
        stepTitle="DIC（デジタル画像相関法）用 動画フレーム高速一括切り出しガイド"
        summary="引張試験等で撮影した動画ファイル（.mp4 / .MP4 / .mov / .avi）から、指定した秒数範囲・時間間隔で静止画フレームを連番画像として高速出力します。日本語を含むフォルダパスでも文字化けやエラーなく保存できます。"
        steps={[
          {
            badge: 'STEP 1',
            title: '処理モードと動画を選択',
            description: '1本の動画なら「単一動画ファイル指定」、フォルダ内の全動画をまとめて処理するなら「フォルダ内全動画一括処理」を選び、「参照」ボタンで選択します。',
          },
          {
            badge: 'STEP 2',
            title: '開始秒数・終了秒数・切り出し間隔を設定',
            description: '例えば 1.0秒おきにフレームを抽出する場合は「step_sec = 1.0」に設定します。右側のカードに出力予定枚数が自動計算されます。',
          },
          {
            badge: 'STEP 3',
            title: '「フレーム画像の一括切り出しを実行」をクリック',
            description: '進捗バーが100%になると、動画と同じ階層（または指定フォルダ）に連番画像ファイルが出力されます。',
          },
        ]}
        glossary={[
          {
            term: 'DIC (Digital Image Correlation / デジタル画像相関法)',
            meaning:
              '試験片表面のランダムなスペックル模様を連続撮影した画像群から、局所ひずみ分布やリュダース帯の伝播を非接触で計測する手法です。',
          },
          {
            term: 'JPEG (.jpg) と PNG (.png ロスレス) の違い',
            meaning:
              'ファイル容量を抑えたい場合はJPEG、圧縮ノイズを完全に排除して最高精度のひずみ解析を行いたい場合はPNG（ロスレス）を選択してください。',
          },
        ]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Mode & Parameters */}
        <div className="lg:col-span-5 space-y-5">
          <div className="panel-card p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/40 flex items-center justify-center text-amber-400">
                  <Film className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base sm:text-lg font-bold text-zinc-100">
                    DIC用 動画フレーム切り出し設定
                  </h2>
                  <p className="text-sm text-zinc-400">
                    単一動画 / フォルダ一括対応・日本語パス完全対応 (`cv2.imencode`)
                  </p>
                </div>
              </div>
            </div>

            {/* Mode Toggle */}
            <div data-tour="dic-mode-select">
              <label className="label-xs block mb-2">STEP 1: 処理モード選択</label>
              <div className="grid grid-cols-2 gap-2.5 p-1.5 bg-zinc-950 rounded-xl border border-zinc-800">
                <button
                  type="button"
                  onClick={() => handleSelectMode('single')}
                  className={`py-2.5 px-3 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${
                    mode === 'single'
                      ? 'bg-cyan-500 text-zinc-950 shadow'
                      : 'text-zinc-300 hover:text-zinc-100'
                  }`}
                >
                  <FileVideo className="w-4 h-4" />
                  単一動画ファイル指定
                </button>
                <button
                  type="button"
                  onClick={() => handleSelectMode('folder')}
                  className={`py-2.5 px-3 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${
                    mode === 'folder'
                      ? 'bg-amber-500 text-zinc-950 shadow'
                      : 'text-zinc-300 hover:text-zinc-100'
                  }`}
                >
                  <FolderOpen className="w-4 h-4" />
                  フォルダ内全動画一括処理
                </button>
              </div>
            </div>

            {/* Target Path Input */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label htmlFor="dic-target-path" className="label-xs">
                  {mode === 'single' ? '対象動画ファイルパス' : '対象動画フォルダパス'}
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
                    className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    サンプル動画をセット
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  id="dic-target-path"
                  type="text"
                  value={targetPath}
                  onChange={(e) => setTargetPath(e.target.value)}
                  placeholder={
                    mode === 'single'
                      ? 'C:\\path\\to\\video.mp4'
                      : 'C:\\path\\to\\video_folder'
                  }
                  className="input-field font-mono text-sm flex-1"
                />
                <button
                  type="button"
                  onClick={handleBrowseTarget}
                  className="btn-secondary shrink-0"
                  title="OSネイティブ選択ダイアログを開く"
                >
                  <FolderOpen className="w-4 h-4 text-amber-400" />
                  参照
                </button>
                <button
                  type="button"
                  onClick={() => handleInspect(targetPath, mode, false)}
                  disabled={loadingInspect || !targetPath.trim()}
                  className="btn-secondary shrink-0"
                  title="メタデータ再取得"
                >
                  <RefreshCw className={`w-4 h-4 ${loadingInspect ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>

            {/* Extraction Timing Parameters */}
            <div data-tour="dic-timing-params" className="grid grid-cols-3 gap-3 pt-1">
              <div>
                <label htmlFor="dic-start-sec" className="label-xs block mb-1.5">
                  開始秒数 `start_sec` (s)
                </label>
                <input
                  id="dic-start-sec"
                  type="number"
                  step="0.1"
                  min="0"
                  value={startSec}
                  onChange={(e) => setStartSec(Math.max(0, parseFloat(e.target.value) || 0))}
                  onBlur={() => handleInspect(targetPath, mode, false)}
                  className="input-field font-mono tabular-nums text-sm"
                />
              </div>
              <div>
                <label htmlFor="dic-stop-sec" className="label-xs block mb-1.5">
                  終了秒数 `stop_sec` (s)
                </label>
                <input
                  id="dic-stop-sec"
                  type="number"
                  step="0.5"
                  min="0.1"
                  value={stopSec}
                  onChange={(e) => setStopSec(Math.max(0.1, parseFloat(e.target.value) || 1.0))}
                  onBlur={() => handleInspect(targetPath, mode, false)}
                  className="input-field font-mono tabular-nums text-sm"
                />
              </div>
              <div>
                <label htmlFor="dic-step-sec" className="label-xs block mb-1.5">
                  切り出し間隔 `step_sec` (s)
                </label>
                <input
                  id="dic-step-sec"
                  type="number"
                  step="0.1"
                  min="0.02"
                  value={stepSec}
                  onChange={(e) => setStepSec(Math.max(0.02, parseFloat(e.target.value) || 1.0))}
                  onBlur={() => handleInspect(targetPath, mode, false)}
                  className="input-field font-mono tabular-nums text-sm"
                />
              </div>
            </div>

            {/* Output Format & Destination */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label htmlFor="dic-ext" className="label-xs block mb-1.5">
                  出力画像形式
                </label>
                <select
                  id="dic-ext"
                  value={ext}
                  onChange={(e) => setExt(e.target.value as 'jpg' | 'png')}
                  className="input-field font-mono text-sm"
                >
                  <option value="jpg">JPEG (.jpg)</option>
                  <option value="png">PNG (.png ロスレス)</option>
                </select>
              </div>
              <div className="col-span-2">
                <label htmlFor="dic-basename" className="label-xs block mb-1.5">
                  {mode === 'single' ? '出力ファイル名プレフィックス' : 'フォルダ一括時サフィックス'}
                </label>
                <input
                  id="dic-basename"
                  type="text"
                  value={basename}
                  onChange={(e) => setBasename(e.target.value)}
                  placeholder={mode === 'single' ? 'video_img' : '_img'}
                  className="input-field font-mono text-sm"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="dic-output-dir" className="label-xs block">
                出力先ディレクトリ（空欄時は動画と同階層に自動作成）
              </label>
              <div className="flex gap-2">
                <input
                  id="dic-output-dir"
                  type="text"
                  value={outputDir}
                  onChange={(e) => setOutputDir(e.target.value)}
                  placeholder="自動設定"
                  className="input-field font-mono text-sm flex-1"
                />
                <button
                  type="button"
                  onClick={handleBrowseOutputDir}
                  className="btn-secondary shrink-0"
                >
                  <FolderOpen className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Action Button */}
            <button
              type="button"
              data-tour="dic-run-btn"
              onClick={handleRunExport}
              disabled={runningExport || !targetPath.trim()}
              className="btn-amber w-full py-3.5 text-base flex items-center justify-center gap-2.5"
            >
              {runningExport ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  フレーム切り出し実行中... ({fmtFixed(progressPct, 1)}%)
                </>
              ) : (
                <>
                  <Play className="w-5 h-5 fill-current" />
                  フレーム画像の一括切り出しを実行
                </>
              )}
            </button>

            {errorMsg && (
              <div className="p-4 rounded-xl bg-red-950/50 border border-red-500/40 text-sm text-red-200 flex items-start gap-2.5">
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <span>{errorMsg}</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Video Metadata & Real-Time Extraction Monitor */}
        <div className="lg:col-span-7 space-y-5">
          {/* Summary KPI Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
            <div className="panel-card p-4">
              <div className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                <Film className="w-4 h-4 text-cyan-400" />
                認識動画ファイル数
              </div>
              <div className="mt-2 text-2xl font-bold font-mono tabular-nums text-zinc-100">
                {inspectData ? inspectData.video_count : 0}{' '}
                <span className="text-xs font-normal text-zinc-400">files</span>
              </div>
            </div>

            <div className="panel-card p-4">
              <div className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-amber-400" />
                総再生時間
              </div>
              <div className="mt-2 text-2xl font-bold font-mono tabular-nums text-zinc-100">
                {inspectData ? fmtFixed(inspectData.total_duration_sec, 2) : '0.00'}{' '}
                <span className="text-xs font-normal text-zinc-400">sec</span>
              </div>
            </div>

            <div className="panel-card p-4">
              <div className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-emerald-400" />
                フレームレート (代表)
              </div>
              <div className="mt-2 text-2xl font-bold font-mono tabular-nums text-zinc-100">
                {inspectData && inspectData.videos[0]
                  ? fmtFixed(inspectData.videos[0].fps, 2)
                  : '0.00'}{' '}
                <span className="text-xs font-normal text-zinc-400">fps</span>
              </div>
            </div>

            <div className="panel-card p-4 border-cyan-500/40">
              <div className="text-xs font-medium text-cyan-300 flex items-center gap-1.5">
                <ImageIcon className="w-4 h-4 text-cyan-400" />
                出力予定枚数 (合計)
              </div>
              <div className="mt-2 text-2xl font-bold font-mono tabular-nums text-cyan-300">
                {inspectData ? inspectData.expected_total_frames : 0}{' '}
                <span className="text-xs font-normal text-cyan-400/80">frames</span>
              </div>
            </div>
          </div>

          {/* Metadata Table */}
          <div className="panel-card p-5 space-y-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-bold text-zinc-200">
                検出された動画メタデータ一覧（大文字 `.MP4` / 小文字 `.mp4` / `.mov` / `.avi` 自動認識）
              </h3>
              <span className="text-sm font-mono tabular-nums text-zinc-300">
                間隔 {fmtFixed(stepSec, 2)}s ({fmtFixed(startSec, 1)}s – {fmtFixed(stopSec, 1)}s)
              </span>
            </div>

            <div className="overflow-x-auto max-h-64 border border-zinc-800 rounded-xl">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="bg-zinc-900/90 border-b border-zinc-800 text-zinc-300">
                    <th className="py-2.5 px-3.5 font-semibold">ファイル名</th>
                    <th className="py-2.5 px-3.5 font-semibold">拡張子</th>
                    <th className="py-2.5 px-3.5 font-semibold text-right">解像度</th>
                    <th className="py-2.5 px-3.5 font-semibold text-right">FPS</th>
                    <th className="py-2.5 px-3.5 font-semibold text-right">総フレーム数</th>
                    <th className="py-2.5 px-3.5 font-semibold text-right">再生時間 (s)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 font-mono tabular-nums">
                  {inspectData && inspectData.videos.length > 0 ? (
                    inspectData.videos.map((v) => (
                      <tr key={v.video_path} className="hover:bg-zinc-800/40">
                        <td className="py-2.5 px-3.5 text-zinc-100 font-sans font-medium">
                          {v.filename}
                        </td>
                        <td className="py-2.5 px-3.5">
                          <span className="px-2 py-0.5 rounded bg-zinc-800 text-cyan-300 text-xs">
                            {v.extension}
                          </span>
                        </td>
                        <td className="py-2.5 px-3.5 text-right text-zinc-200">
                          {v.width}×{v.height}
                        </td>
                        <td className="py-2.5 px-3.5 text-right text-zinc-200">
                          {fmtFixed(v.fps, 2)}
                        </td>
                        <td className="py-2.5 px-3.5 text-right text-zinc-200">{v.frame_count}</td>
                        <td className="py-2.5 px-3.5 text-right text-amber-300 font-bold">
                          {fmtFixed(v.duration_sec, 2)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-zinc-400 font-sans">
                        動画ファイルまたはフォルダを選択するとメタデータが表示されます
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Live Progress & Completion Status */}
          <div className="panel-card p-5 space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-zinc-200">
                切り出し進捗モニター
              </span>
              <span className="text-sm font-mono tabular-nums text-cyan-400 font-bold">
                {fmtFixed(progressPct, 1)}% ({currentCount}/{totalCount || (inspectData?.expected_total_frames ?? 0)})
              </span>
            </div>

            <div className="w-full h-3 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-amber-500 transition-all duration-150"
                style={{ width: `${Math.min(100, Math.max(0, progressPct))}%` }}
              />
            </div>

            {progressDetail && (
              <p className="text-sm font-mono tabular-nums text-zinc-300 truncate">
                {progressDetail}
              </p>
            )}

            {exportResult && (
              <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/40 space-y-2">
                <div className="flex items-center gap-2 text-emerald-300 text-sm font-bold">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  <span>
                    DICフレーム画像の一括出力が完了しました（合計{' '}
                    <strong className="font-mono tabular-nums">
                      {exportResult.saved_count ?? exportResult.total_saved_frames ?? 0}
                    </strong>{' '}
                    枚保存）
                  </span>
                </div>
                <div className="text-sm font-mono text-zinc-200 break-all">
                  出力先: {exportResult.output_dir || exportResult.output_root_dir}
                </div>
                {exportResult.sample_files && exportResult.sample_files.length > 0 && (
                  <div className="text-xs font-mono text-zinc-400">
                    先頭ファイル例: {exportResult.sample_files[0]}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
