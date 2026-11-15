import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Wrench,
  CheckSquare,
  Square,
  Sparkles,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Layers,
  TrendingUp,
  Plus,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { TutorialGuideBanner } from './TutorialGuideBanner';
import { apiGet, apiPost, fmtFixed } from '../lib/utils';
import type {
  BatchGroupResult,
  BatchRefitResponse,
  CandidateFitResult,
} from '../types/xrd';

export interface Step4ReviewExportProps {
  folderPath: string;
  specimenName: string;
  batchResults: Record<string, BatchGroupResult>;
  setBatchResults: React.Dispatch<React.SetStateAction<Record<string, BatchGroupResult>>>;
  onProceedStep5: () => void;
}

interface InspectedWaveform {
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

export interface OutlierQueueItem {
  key: string; // `${group_id}::${num}`
  group_id: string;
  sheet_name: string;
  peaks: string[];
  phaseLabel: string;
  hasGamma: boolean;
  hasAlpha: boolean;
  num: number;
  isFlaggedOutlier: boolean;
}

type Step4SubScreen = 'outlier_studio' | 'trend_and_export';

export const Step4ReviewExport: React.FC<Step4ReviewExportProps> = ({
  folderPath,
  specimenName,
  batchResults,
  setBatchResults,
  onProceedStep5,
}) => {
  const groupIds = useMemo(() => Object.keys(batchResults), [batchResults]);
  const [subScreen, setSubScreen] = useState<Step4SubScreen>('outlier_studio');

  // --- All Outlier Items across ALL Phases & Peak Groups ---
  const [customAddedItems, setCustomAddedItems] = useState<OutlierQueueItem[]>([]);
  const [selectedKeys, setSelectedKeys] = useState<Record<string, boolean>>({});
  const [activeQueueIndex, setActiveQueueIndex] = useState<number>(0);

  // Add arbitrary (group_id, num) to queue
  const [manualGroupId, setManualGroupId] = useState<string>(groupIds[0] || '');
  const [manualNumInput, setManualNumInput] = useState<string>('');

  useEffect(() => {
    if (groupIds.length > 0 && (!manualGroupId || !batchResults[manualGroupId])) {
      setManualGroupId(groupIds[0]);
    }
  }, [groupIds, manualGroupId, batchResults]);

  const allQueueCandidates = useMemo<OutlierQueueItem[]>(() => {
    const list: OutlierQueueItem[] = [];
    const seen = new Set<string>();

    for (const gid of groupIds) {
      const grp = batchResults[gid];
      if (!grp) continue;
      const hasGamma = grp.peaks.some((p) => p.toLowerCase().startsWith('fcc'));
      const hasAlpha = grp.peaks.some((p) => p.toLowerCase().startsWith('bcc'));
      const phaseLabel =
        hasGamma && hasAlpha
          ? "γ-FCC + α'-BCC 重畳"
          : hasGamma
          ? 'γ-FCC (オーステナイト)'
          : "α'-BCC (マルテンサイト)";

      for (const num of grp.outlier_nums || []) {
        const key = `${gid}::${num}`;
        seen.add(key);
        list.push({
          key,
          group_id: gid,
          sheet_name: grp.sheet_name,
          peaks: grp.peaks,
          phaseLabel,
          hasGamma,
          hasAlpha,
          num,
          isFlaggedOutlier: true,
        });
      }
    }

    for (const item of customAddedItems) {
      if (!seen.has(item.key) && batchResults[item.group_id]) {
        seen.add(item.key);
        list.push(item);
      }
    }

    return list;
  }, [groupIds, batchResults, customAddedItems]);

  // Auto-select all flagged outliers on initial load
  useEffect(() => {
    if (allQueueCandidates.length > 0 && Object.keys(selectedKeys).length === 0) {
      const nextSel: Record<string, boolean> = {};
      for (const item of allQueueCandidates) {
        nextSel[item.key] = true;
      }
      setSelectedKeys(nextSel);
    }
  }, [allQueueCandidates.length]);

  const checkedQueueItems = useMemo(
    () => allQueueCandidates.filter((it) => selectedKeys[it.key]),
    [allQueueCandidates, selectedKeys]
  );

  const activeQueueItem: OutlierQueueItem | null = useMemo(() => {
    if (checkedQueueItems.length > 0) {
      const safeIdx = Math.min(Math.max(0, activeQueueIndex), checkedQueueItems.length - 1);
      return checkedQueueItems[safeIdx];
    }
    return allQueueCandidates[0] || null;
  }, [checkedQueueItems, activeQueueIndex, allQueueCandidates]);

  // --- Trend & Inspection State ---
  const [activeTrendGroupId, setActiveTrendGroupId] = useState<string>(groupIds[0] || '');
  useEffect(() => {
    if (groupIds.length > 0 && (!activeTrendGroupId || !batchResults[activeTrendGroupId])) {
      setActiveTrendGroupId(groupIds[0]);
    }
  }, [groupIds, activeTrendGroupId, batchResults]);

  const [inspected, setInspected] = useState<InspectedWaveform | null>(null);
  const [loadingWaveform, setLoadingWaveform] = useState<boolean>(false);
  const [refittingSingle, setRefittingSingle] = useState<boolean>(false);
  const [refittingBatch, setRefittingBatch] = useState<boolean>(false);
  const [exporting, setExporting] = useState<boolean>(false);
  const [exportInfo, setExportInfo] = useState<{ saved_path: string; sheets: string[] } | null>(
    null
  );
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Editable repair parameters for the currently active queue item
  const [repairRangeMin, setRepairRangeMin] = useState<number>(11.0);
  const [repairRangeMax, setRepairRangeMax] = useState<number>(12.0);
  const [repairCenters, setRepairCenters] = useState<number[]>([]);
  const [repairWGs, setRepairWGs] = useState<number[]>([]);
  const [repairWLs, setRepairWLs] = useState<number[]>([]);
  const [repairAreas, setRepairAreas] = useState<number[]>([]);
  const [repairVaryY0, setRepairVaryY0] = useState<boolean>(false);

  const loadWaveformForItem = useCallback(
    async (gid: string, num: number) => {
      const grp = batchResults[gid];
      if (!grp) return;
      setLoadingWaveform(true);
      setErrorMsg(null);
      try {
        const res = await apiGet<InspectedWaveform>(
          `/api/fitting/waveform/${encodeURIComponent(gid)}/${num}?folder_path=${encodeURIComponent(
            folderPath
          )}`
        );
        setInspected(res);
        setRepairRangeMin(grp.th_min);
        setRepairRangeMax(grp.th_max);
        const r = res.row_data || {};
        setRepairCenters(grp.peaks.map((pk) => Number(r[`2th_${pk}`] ?? 12.0)));
        setRepairWGs(grp.peaks.map((pk) => Number(r[`wG_${pk}`] ?? 0.02)));
        setRepairWLs(grp.peaks.map((pk) => Number(r[`wL_${pk}`] ?? 0.015)));
        setRepairAreas(grp.peaks.map((pk) => Number(r[`I_${pk}`] ?? 100.0)));
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        setLoadingWaveform(false);
      }
    },
    [batchResults, folderPath]
  );

  // Load waveform whenever activeQueueItem changes
  useEffect(() => {
    if (activeQueueItem) {
      loadWaveformForItem(activeQueueItem.group_id, activeQueueItem.num);
    }
  }, [activeQueueItem?.key, loadWaveformForItem]);

  // --- Batch Selection Helpers ---
  const handleSelectAll = () => {
    const next: Record<string, boolean> = {};
    for (const it of allQueueCandidates) next[it.key] = true;
    setSelectedKeys(next);
    setActiveQueueIndex(0);
  };

  const handleSelectPhase = (phase: 'gamma' | 'alpha') => {
    const next: Record<string, boolean> = {};
    for (const it of allQueueCandidates) {
      next[it.key] = phase === 'gamma' ? it.hasGamma : it.hasAlpha;
    }
    setSelectedKeys(next);
    setActiveQueueIndex(0);
  };

  const handleClearSelection = () => {
    setSelectedKeys({});
  };

  const handleAddManualNums = () => {
    const grp = batchResults[manualGroupId];
    if (!grp || !manualNumInput.trim()) return;
    const nums = manualNumInput
      .split(/[,\s]+/)
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !Number.isNaN(n));
    if (nums.length === 0) return;

    const hasGamma = grp.peaks.some((p) => p.toLowerCase().startsWith('fcc'));
    const hasAlpha = grp.peaks.some((p) => p.toLowerCase().startsWith('bcc'));
    const phaseLabel =
      hasGamma && hasAlpha
        ? "γ-FCC + α'-BCC 重畳"
        : hasGamma
        ? 'γ-FCC (オーステナイト)'
        : "α'-BCC (マルテンサイト)";

    const newItems: OutlierQueueItem[] = nums.map((num) => ({
      key: `${manualGroupId}::${num}`,
      group_id: manualGroupId,
      sheet_name: grp.sheet_name,
      peaks: grp.peaks,
      phaseLabel,
      hasGamma,
      hasAlpha,
      num,
      isFlaggedOutlier: (grp.outlier_nums || []).includes(num),
    }));

    setCustomAddedItems((prev) => [...prev, ...newItems]);
    setSelectedKeys((prev) => {
      const next = { ...prev };
      for (const it of newItems) next[it.key] = true;
      return next;
    });
    setManualNumInput('');
  };

  // --- 1. Batch Smart Auto-Refit All Selected Items across All Phases ---
  const handleBatchAutoRefitSelected = async () => {
    if (checkedQueueItems.length === 0) return;
    setRefittingBatch(true);
    setErrorMsg(null);
    setStatusMessage(null);
    try {
      const res = await apiPost<BatchRefitResponse>('/api/fitting/refit-batch', {
        folder_path: folderPath,
        use_neighbor_interpolation: true,
        vary_y0: repairVaryY0,
        items: checkedQueueItems.map((it) => ({
          group_id: it.group_id,
          num: it.num,
          peaks: it.peaks,
        })),
      });

      // Update batchResults state with all repaired rows
      setBatchResults((prev) => {
        const next = { ...prev };
        for (const rep of res.repaired_items) {
          const grp = next[rep.group_id];
          if (!grp) continue;
          const updatedRows = grp.rows.map((r) =>
            Number(r.num) === rep.num ? rep.updated_row : r
          );
          const updatedOutliers = (grp.outlier_nums || []).filter((n) => n !== rep.num);
          next[rep.group_id] = {
            ...grp,
            rows: updatedRows,
            outlier_nums: updatedOutliers,
          };
        }
        return next;
      });

      if (res.saved_path) {
        setExportInfo({
          saved_path: res.saved_path,
          sheets: Object.values(batchResults).map((g) => g.sheet_name),
        });
      }
      setStatusMessage(
        `選択した ${res.repaired_count} 件（複数相・全対象ピーク）の要確認フレームを一括スマート再フィットし、解析ディレクトリの output.xlsx を自動更新しました。`
      );
      if (activeQueueItem) {
        await loadWaveformForItem(activeQueueItem.group_id, activeQueueItem.num);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setRefittingBatch(false);
    }
  };

  // --- 2. Apply Current Individual Parameters to All Selected Items in the Same Group ---
  const handleApplyCurrentParamsToSelectedInGroup = async () => {
    if (!activeQueueItem) return;
    const sameGroupItems = checkedQueueItems.filter(
      (it) => it.group_id === activeQueueItem.group_id
    );
    if (sameGroupItems.length === 0) return;

    setRefittingBatch(true);
    setErrorMsg(null);
    setStatusMessage(null);
    try {
      const res = await apiPost<BatchRefitResponse>('/api/fitting/refit-batch', {
        folder_path: folderPath,
        use_neighbor_interpolation: false,
        vary_y0: repairVaryY0,
        items: sameGroupItems.map((it) => ({
          group_id: it.group_id,
          num: it.num,
          peaks: it.peaks,
          range_min: repairRangeMin,
          range_max: repairRangeMax,
          initial_centers: repairCenters,
          initial_wG: repairWGs,
          initial_wL: repairWLs,
          initial_A: repairAreas,
          vary_y0: repairVaryY0,
        })),
      });

      setBatchResults((prev) => {
        const next = { ...prev };
        for (const rep of res.repaired_items) {
          const grp = next[rep.group_id];
          if (!grp) continue;
          next[rep.group_id] = {
            ...grp,
            rows: grp.rows.map((r) => (Number(r.num) === rep.num ? rep.updated_row : r)),
            outlier_nums: (grp.outlier_nums || []).filter((n) => n !== rep.num),
          };
        }
        return next;
      });

      setStatusMessage(
        `グループ [${activeQueueItem.sheet_name}] の選択中 ${res.repaired_count} 件に現在の初期値・範囲設定を一括適用して個別フィットしました。`
      );
      await loadWaveformForItem(activeQueueItem.group_id, activeQueueItem.num);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setRefittingBatch(false);
    }
  };

  // --- 3. Refit Current Single Item & Advance Queue ---
  const handleRepairSingleAndNext = async (advanceAfter = true) => {
    if (!activeQueueItem) return;
    setRefittingSingle(true);
    setErrorMsg(null);
    setStatusMessage(null);
    try {
      const res = await apiPost<{
        status: string;
        num: number;
        updated_row: Record<string, number>;
        fit: CandidateFitResult;
      }>('/api/fitting/refit-file', {
        folder_path: folderPath,
        group_id: activeQueueItem.group_id,
        num: activeQueueItem.num,
        peaks: activeQueueItem.peaks,
        range_min: repairRangeMin,
        range_max: repairRangeMax,
        initial_centers: repairCenters,
        initial_wG: repairWGs,
        initial_wL: repairWLs,
        initial_A: repairAreas,
        vary_y0: repairVaryY0,
      });

      setInspected({
        num: res.num,
        filename: res.fit.filename,
        residual_rmse: res.fit.rmse,
        relative_residual: res.fit.relative_residual,
        is_outlier: false,
        row_data: res.updated_row,
        waveform: {
          x: res.fit.x,
          y_obs: res.fit.y_obs,
          y_fit: res.fit.y_fit,
          components: res.fit.components,
        },
      });

      // Keep custom items so user can still see what they just fixed in the queue if desired
      setCustomAddedItems((prev) => {
        if (prev.some((p) => p.key === activeQueueItem.key)) return prev;
        return [...prev, { ...activeQueueItem, isFlaggedOutlier: false }];
      });

      setBatchResults((prev) => {
        const grp = prev[activeQueueItem.group_id];
        if (!grp) return prev;
        const updatedRows = grp.rows.map((r) =>
          Number(r.num) === res.num ? res.updated_row : r
        );
        const updatedOutliers = (grp.outlier_nums || []).filter((n) => n !== res.num);
        return {
          ...prev,
          [activeQueueItem.group_id]: {
            ...grp,
            rows: updatedRows,
            outlier_nums: updatedOutliers,
          },
        };
      });

      setStatusMessage(
        `[${activeQueueItem.sheet_name}] num=#${res.num} の個別再フィットを適用し、解析ディレクトリの output.xlsx を自動更新しました (R²=${fmtFixed(
          res.fit.r_squared,
          4
        )})。`
      );

      if (advanceAfter && activeQueueIndex + 1 < checkedQueueItems.length) {
        setActiveQueueIndex((idx) => idx + 1);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setRefittingSingle(false);
    }
  };

  // --- Export Excel ---
  const handleExportExcel = async () => {
    setExporting(true);
    setErrorMsg(null);
    try {
      const sheetPayload = Object.values(batchResults).map((grp) => ({
        sheet_name: grp.sheet_name,
        peaks: grp.peaks,
        rows: grp.rows,
        best_R: grp.best_R,
        history_R: grp.history_R,
        history_residual: grp.history_residual,
      }));
      const res = await apiPost<{
        status: string;
        saved_path: string;
        used_fallback: boolean;
        sheets: string[];
      }>('/api/fitting/export', {
        folder_path: folderPath,
        specimen_name: specimenName || undefined,
        groups: sheetPayload,
      });
      setExportInfo({ saved_path: res.saved_path, sheets: res.sheets });
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(false);
    }
  };

  // --- Waveform Chart Traces ---
  const waveformTraces = useMemo(() => {
    if (!inspected?.waveform) return [];
    const wf = inspected.waveform;
    const traces: Record<string, unknown>[] = [
      {
        x: wf.x,
        y: wf.y_obs,
        type: 'scatter',
        mode: 'markers',
        name: `観測データ (#${inspected.num})`,
        marker: { color: '#a1a1aa', size: 5 },
      },
      {
        x: wf.x,
        y: wf.y_fit,
        type: 'scatter',
        mode: 'lines',
        name: '合成Voigtフィット',
        line: { color: '#10B981', width: 2.8 },
      },
    ];
    for (const [pk, compY] of Object.entries(wf.components || {})) {
      const isFcc = pk.toLowerCase().startsWith('fcc');
      traces.push({
        x: wf.x,
        y: compY,
        type: 'scatter',
        mode: 'lines',
        fill: 'tozeroy',
        name: `${pk} (${isFcc ? 'γ-FCC' : "α'-BCC"})`,
        line: {
          color: isFcc ? '#06B6D4' : '#F59E0B',
          width: 2,
          dash: 'dot',
        },
        fillcolor: isFcc ? 'rgba(6, 182, 212, 0.12)' : 'rgba(245, 158, 11, 0.12)',
      });
    }
    return traces;
  }, [inspected]);

  // --- Trend Chart Traces for Screen 4-B ---
  const activeTrendGroup = batchResults[activeTrendGroupId];
  const trendTraces = useMemo(() => {
    if (!activeTrendGroup) return { twoTh: [], area: [], fwhm: [], residual: [] };
    const nums = activeTrendGroup.rows.map((r) => r.num);
    const outlierSet = new Set(activeTrendGroup.outlier_nums || []);

    const twoTh: Record<string, unknown>[] = [];
    const area: Record<string, unknown>[] = [];
    const fwhm: Record<string, unknown>[] = [];

    activeTrendGroup.peaks.forEach((pk) => {
      const isFcc = pk.toLowerCase().startsWith('fcc');
      const baseColor = isFcc ? '#06B6D4' : '#F59E0B';
      const markerColors = nums.map((n) => (outlierSet.has(n) ? '#EF4444' : baseColor));
      const markerSizes = nums.map((n) => (outlierSet.has(n) ? 9 : 6));

      twoTh.push({
        x: nums,
        y: activeTrendGroup.rows.map((r) => r[`2th_${pk}`]),
        type: 'scatter',
        mode: 'lines+markers',
        name: `2θ_${pk}`,
        line: { color: baseColor, width: 2 },
        marker: { color: markerColors, size: markerSizes },
      });

      area.push({
        x: nums,
        y: activeTrendGroup.rows.map((r) => r[`I_${pk}`]),
        type: 'scatter',
        mode: 'lines+markers',
        name: `I_${pk}`,
        line: { color: baseColor, width: 2 },
        marker: { color: markerColors, size: markerSizes },
      });

      fwhm.push({
        x: nums,
        y: activeTrendGroup.rows.map((r) => r[`FWHM_${pk}`]),
        type: 'scatter',
        mode: 'lines+markers',
        name: `FWHM_${pk}`,
        line: { color: baseColor, width: 2 },
        marker: { color: markerColors, size: markerSizes },
      });
    });

    const residual: Record<string, unknown>[] = [
      {
        x: nums,
        y: activeTrendGroup.rows.map((r) => r.residual ?? 0),
        type: 'scatter',
        mode: 'lines+markers',
        name: 'residual (相対残差)',
        line: { color: '#10B981', width: 2 },
        marker: {
          color: nums.map((n) => (outlierSet.has(n) ? '#EF4444' : '#10B981')),
          size: nums.map((n) => (outlierSet.has(n) ? 9 : 5)),
        },
      },
    ];

    return { twoTh, area, fwhm, residual };
  }, [activeTrendGroup]);

  return (
    <div className="space-y-6">
      {/* Beginner Tutorial Guide Banner */}
      <TutorialGuideBanner
        mode="xrd"
        stepTitle="Step 4: 全相・要確認フィットの一括選択＆個別フィット修復・Excel出力"
        summary="連続フィッティング後に残差が大きかった要確認フレーム（num）を全相（γ相・α'相）まとめて一括選択し、一括スマート修復または順番に個別フィットできます。"
        steps={[
          {
            badge: '手順 1',
            title: '各相の要確認 num を一括選択（または任意の num を追加）',
            description:
              '左側のリストに全ピークグループの要確認 num が表示されます。「すべて一括選択」「γ相のみ」「α\'相のみ」でまとめて選択できます。',
          },
          {
            badge: '手順 2',
            title: '一括スマート再フィット または 順番に個別フィット',
            description:
              '「選択項目を一括スマート再フィット」で前後フレーム補間によりまとめて修復するか、右側のワークベンチで1件ずつ確認しながら個別フィットできます。',
          },
          {
            badge: '手順 3',
            title: 'output.xlsx に保存して Step 5（相分率・転位密度解析）へ',
            description:
              '修復が完了したら「output.xlsx 一括出力」を押し、「Step 5: 相分率・転位密度グラフへ進む」で材料組織解析へ進みます。',
          },
        ]}
        tip="一画面がごちゃつかないよう、「① 要確認フィットの一括選択＆個別修復画面」と「② パラメータ推移グラフ＆データ表画面」をタブで切り替えられる設計になっています。"
      />

      {/* Top Action & Screen Switch Bar */}
      <div className="panel-card p-5 flex flex-wrap items-center justify-between gap-4">
        <div data-tour="step4-subscreen-tabs" className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => setSubScreen('outlier_studio')}
            className={`px-5 py-3 rounded-xl text-sm sm:text-base font-bold transition-all flex items-center gap-2 ${
              subScreen === 'outlier_studio'
                ? 'bg-cyan-500 text-zinc-950 shadow-md shadow-cyan-500/20'
                : 'bg-zinc-800/90 text-zinc-200 hover:bg-zinc-700'
            }`}
          >
            <Wrench className="w-5 h-5" />
            <span>① 要確認フィット 一括選択 ＆ 個別フィット修復 ({allQueueCandidates.length}件)</span>
          </button>

          <button
            type="button"
            onClick={() => setSubScreen('trend_and_export')}
            className={`px-5 py-3 rounded-xl text-sm sm:text-base font-bold transition-all flex items-center gap-2 ${
              subScreen === 'trend_and_export'
                ? 'bg-cyan-500 text-zinc-950 shadow-md shadow-cyan-500/20'
                : 'bg-zinc-800/90 text-zinc-200 hover:bg-zinc-700'
            }`}
          >
            <Layers className="w-5 h-5" />
            <span>② 全ピーク推移グラフ ＆ データテーブル確認</span>
          </button>
        </div>

        <div data-tour="step4-export-btn" className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleExportExcel}
            disabled={exporting || groupIds.length === 0}
            className="btn-emerald"
          >
            {exporting ? (
              <RefreshCw className="w-5 h-5 animate-spin" />
            ) : (
              <FileSpreadsheet className="w-5 h-5" />
            )}
            <span>
              解析ディレクトリへ（{specimenName || '試料'}）output.xlsx を保存・更新
            </span>
          </button>

          <button
            type="button"
            onClick={onProceedStep5}
            className="btn-amber"
          >
            <TrendingUp className="w-5 h-5" />
            <span>Step 5: マルテンサイト相分率・転位密度解析へ進む</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Notifications */}
      {exportInfo && (
        <div className="p-4 rounded-xl bg-emerald-950/50 border border-emerald-500/50 text-sm text-emerald-200 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>
              <strong>Excel出力完了：</strong>{' '}
              <code className="font-mono text-emerald-100">{exportInfo.saved_path}</code>{' '}
              （シート: {exportInfo.sheets.join(', ')} ＋ Physical_Analysis）
            </span>
          </div>
        </div>
      )}

      {statusMessage && (
        <div className="p-4 rounded-xl bg-cyan-950/50 border border-cyan-500/40 text-sm text-cyan-200 flex items-center gap-2.5">
          <Sparkles className="w-5 h-5 text-cyan-400 shrink-0" />
          <span>{statusMessage}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-950/50 border border-red-500/40 text-sm text-red-200 flex items-center gap-2.5">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* =====================================================================
          SUB-SCREEN 4-A: Batch Outlier Selection & Queued Individual Fitting
         ===================================================================== */}
      {subScreen === 'outlier_studio' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Multi-Phase Outlier Batch Checklist */}
          <div className="lg:col-span-5 panel-card p-5 space-y-4 flex flex-col">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <h3 className="text-lg font-bold text-zinc-100">
                  各相・全ピークの「要確認 num」一括選択リスト
                </h3>
                <p className="text-sm text-zinc-400">
                  チェックを入れた項目をまとめて再フィット、または順番に個別フィットできます
                </p>
              </div>
              <span className="px-3 py-1 rounded-full bg-cyan-500/20 border border-cyan-500/40 text-sm font-mono font-bold text-cyan-300 tabular-nums">
                選択中: {checkedQueueItems.length} / {allQueueCandidates.length}
              </span>
            </div>

            {/* Batch Selection Filter Buttons */}
            <div data-tour="step4-batch-select" className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleSelectAll}
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-xs sm:text-sm font-medium text-zinc-100 flex items-center gap-1.5"
              >
                <CheckSquare className="w-4 h-4 text-cyan-400" />
                すべて一括選択
              </button>
              <button
                type="button"
                onClick={() => handleSelectPhase('gamma')}
                className="px-3 py-1.5 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/60 border border-cyan-500/40 text-xs sm:text-sm font-medium text-cyan-200"
              >
                γ-FCC相を一括選択
              </button>
              <button
                type="button"
                onClick={() => handleSelectPhase('alpha')}
                className="px-3 py-1.5 rounded-lg bg-amber-950/60 hover:bg-amber-900/60 border border-amber-500/40 text-xs sm:text-sm font-medium text-amber-200"
              >
                α&apos;-BCC相を一括選択
              </button>
              <button
                type="button"
                onClick={handleClearSelection}
                className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs sm:text-sm text-zinc-400"
              >
                選択解除
              </button>
            </div>

            {/* Primary Batch Action Button */}
            <button
              type="button"
              data-tour="step4-batch-refit-btn"
              onClick={handleBatchAutoRefitSelected}
              disabled={refittingBatch || checkedQueueItems.length === 0}
              className="btn-primary w-full py-3"
            >
              {refittingBatch ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  <span>選択した {checkedQueueItems.length} 件を一括スマート再フィット中...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>
                    選択した {checkedQueueItems.length} 件（全相）を一括スマート再フィット
                  </span>
                </>
              )}
            </button>

            {/* Checklist Table */}
            <div className="overflow-y-auto max-h-[380px] border border-zinc-800 rounded-xl divide-y divide-zinc-800/70">
              {allQueueCandidates.length > 0 ? (
                allQueueCandidates.map((item) => {
                  const isChecked = Boolean(selectedKeys[item.key]);
                  const isCurrentActive = activeQueueItem?.key === item.key;
                  const checkedIdx = checkedQueueItems.findIndex((c) => c.key === item.key);

                  return (
                    <div
                      key={item.key}
                      onClick={() => {
                        if (!isChecked) {
                          setSelectedKeys((prev) => ({ ...prev, [item.key]: true }));
                        }
                        if (checkedIdx >= 0) {
                          setActiveQueueIndex(checkedIdx);
                        } else {
                          loadWaveformForItem(item.group_id, item.num);
                        }
                      }}
                      className={`p-3.5 flex items-center justify-between gap-3 cursor-pointer transition-colors ${
                        isCurrentActive
                          ? 'bg-cyan-500/15 border-l-4 border-l-cyan-400'
                          : 'hover:bg-zinc-800/50'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedKeys((prev) => ({
                              ...prev,
                              [item.key]: !prev[item.key],
                            }));
                          }}
                          className="text-cyan-400 hover:text-cyan-300 shrink-0"
                        >
                          {isChecked ? (
                            <CheckSquare className="w-5 h-5" />
                          ) : (
                            <Square className="w-5 h-5 text-zinc-500" />
                          )}
                        </button>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-base font-bold font-mono tabular-nums text-zinc-100">
                              num #{item.num}
                            </span>
                            <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-zinc-800 text-cyan-300 border border-zinc-700">
                              {item.peaks.join(' + ')}
                            </span>
                          </div>
                          <div className="text-xs text-zinc-400 mt-0.5">{item.phaseLabel}</div>
                        </div>
                      </div>

                      <div className="shrink-0">
                        {item.isFlaggedOutlier ? (
                          <span className="px-2.5 py-1 rounded-full bg-amber-500/20 border border-amber-500/40 text-xs font-semibold text-amber-300">
                            要確認
                          </span>
                        ) : (
                          <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-xs font-semibold text-emerald-300">
                            修復済 / 任意
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-8 text-center space-y-2">
                  <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto" />
                  <div className="text-base font-bold text-zinc-200">
                    現在、自動検出された要確認（外れ値）フレームはありません
                  </div>
                  <p className="text-sm text-zinc-400">
                    下の入力欄から任意のファイル番号（num）を追加して一括・個別フィットすることも可能です。
                  </p>
                </div>
              )}
            </div>

            {/* Add Arbitrary `num` to the Batch/Individual Queue */}
            <div className="pt-3 border-t border-zinc-800 space-y-2">
              <label className="text-sm font-semibold text-zinc-300 block">
                任意のフレーム番号（num）を個別フィット対象に追加（カンマ区切りで複数可）
              </label>
              <div className="flex flex-wrap sm:flex-nowrap gap-2">
                <select
                  value={manualGroupId}
                  onChange={(e) => setManualGroupId(e.target.value)}
                  className="input-field sm:w-44 font-mono text-sm"
                >
                  {groupIds.map((gid) => (
                    <option key={gid} value={gid}>
                      {batchResults[gid]?.peaks.join('+') || gid}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={manualNumInput}
                  onChange={(e) => setManualNumInput(e.target.value)}
                  placeholder="例: 50, 450, 900"
                  className="input-field font-mono text-sm flex-1"
                />
                <button
                  type="button"
                  onClick={handleAddManualNums}
                  className="btn-secondary shrink-0"
                >
                  <Plus className="w-4 h-4" />
                  <span>リストに追加</span>
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Individual Fit Workbench with Queue Navigation */}
          <div className="lg:col-span-7 panel-card p-5 space-y-5">
            {activeQueueItem ? (
              <>
                {/* Queue Navigator Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-zinc-950 border border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setActiveQueueIndex((idx) => Math.max(0, idx - 1))}
                    disabled={activeQueueIndex <= 0}
                    className="btn-secondary py-2 px-3"
                  >
                    <ChevronLeft className="w-4 h-4" />
                    <span>前の選択項目</span>
                  </button>

                  <div className="text-center">
                    <div className="text-xs font-mono uppercase tracking-wider text-cyan-400">
                      選択リスト 連続個別フィット ({Math.min(activeQueueIndex + 1, Math.max(1, checkedQueueItems.length))} /{' '}
                      {Math.max(1, checkedQueueItems.length)} 件目)
                    </div>
                    <div className="text-lg font-bold text-zinc-100 font-mono tabular-nums mt-0.5">
                      [{activeQueueItem.peaks.join(' + ')}] — ファイル番号 num #{activeQueueItem.num}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      setActiveQueueIndex((idx) =>
                        Math.min(Math.max(0, checkedQueueItems.length - 1), idx + 1)
                      )
                    }
                    disabled={activeQueueIndex >= checkedQueueItems.length - 1}
                    className="btn-secondary py-2 px-3"
                  >
                    <span>次の選択項目</span>
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>

                {/* Large Waveform & Component Separation Plot */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-zinc-200">
                      観測波形・Voigtフィット波形・各相成分プロファイル
                    </span>
                    {inspected && (
                      <span className="font-mono tabular-nums text-zinc-300">
                        残差 RMSE: {fmtFixed(inspected.residual_rmse, 3)} / 相対残差:{' '}
                        {fmtFixed(inspected.relative_residual * 100, 2)}%
                      </span>
                    )}
                  </div>

                  <PlotlyChart
                    data={waveformTraces}
                    layout={{
                      xaxis: { title: '回折角 2θ (deg)' },
                      yaxis: { title: '強度 Intensity (a.u.)' },
                    }}
                    className="w-full h-[340px]"
                  />
                </div>

                {/* Individual Peak Parameter Controls */}
                <div className="space-y-4 pt-2 border-t border-zinc-800">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="label-sm block mb-1">
                        フィット範囲 最小 `2θ_min` (deg)
                      </label>
                      <input
                        type="number"
                        step="0.05"
                        value={repairRangeMin}
                        onChange={(e) => setRepairRangeMin(parseFloat(e.target.value) || 10.0)}
                        className="input-field font-mono tabular-nums"
                      />
                    </div>
                    <div>
                      <label className="label-sm block mb-1">
                        フィット範囲 最大 `2θ_max` (deg)
                      </label>
                      <input
                        type="number"
                        step="0.05"
                        value={repairRangeMax}
                        onChange={(e) => setRepairRangeMax(parseFloat(e.target.value) || 24.0)}
                        className="input-field font-mono tabular-nums"
                      />
                    </div>
                    <div className="flex items-end pb-1">
                      <label className="flex items-center gap-2.5 text-sm text-zinc-200 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={repairVaryY0}
                          onChange={(e) => setRepairVaryY0(e.target.checked)}
                          className="w-4 h-4 rounded border-zinc-600 text-cyan-500 focus:ring-cyan-500"
                        />
                        <span>ベースラインオフセット `y0` も微調整する</span>
                      </label>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {activeQueueItem.peaks.map((pk, idx) => {
                      const isFcc = pk.toLowerCase().startsWith('fcc');
                      return (
                        <div
                          key={pk}
                          className="p-3.5 rounded-xl bg-zinc-950/90 border border-zinc-800 space-y-2"
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2.5 py-0.5 rounded text-xs font-mono font-bold ${
                                isFcc
                                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                                  : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                              }`}
                            >
                              {pk} ({isFcc ? 'γ-FCC相' : "α'-BCC相"})
                            </span>
                            <span className="text-xs text-zinc-400">
                              初期値の指定（空欄やそのままで再フィット可能）
                            </span>
                          </div>

                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            <div>
                              <label className="text-xs text-zinc-400 block mb-1">
                                中心角 `2θ` (deg)
                              </label>
                              <input
                                type="number"
                                step="0.005"
                                value={repairCenters[idx] ?? 12.0}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value) || 0;
                                  setRepairCenters((prev) =>
                                    prev.map((v, i) => (i === idx ? val : v))
                                  );
                                }}
                                className="input-field py-1.5 text-sm font-mono tabular-nums"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-zinc-400 block mb-1">
                                積分強度 `A`
                              </label>
                              <input
                                type="number"
                                step="10"
                                value={repairAreas[idx] ?? 100}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value) || 0;
                                  setRepairAreas((prev) =>
                                    prev.map((v, i) => (i === idx ? val : v))
                                  );
                                }}
                                className="input-field py-1.5 text-sm font-mono tabular-nums"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-zinc-400 block mb-1">
                                ガウス幅 `wG` (deg)
                              </label>
                              <input
                                type="number"
                                step="0.002"
                                value={repairWGs[idx] ?? 0.02}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value) || 0.005;
                                  setRepairWGs((prev) =>
                                    prev.map((v, i) => (i === idx ? val : v))
                                  );
                                }}
                                className="input-field py-1.5 text-sm font-mono tabular-nums"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-zinc-400 block mb-1">
                                ローレンツ幅 `wL` (deg)
                              </label>
                              <input
                                type="number"
                                step="0.002"
                                value={repairWLs[idx] ?? 0.015}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value) || 0.002;
                                  setRepairWLs((prev) =>
                                    prev.map((v, i) => (i === idx ? val : v))
                                  );
                                }}
                                className="input-field py-1.5 text-sm font-mono tabular-nums"
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Action Buttons for Individual & Group-Batch Fit */}
                  <div className="flex flex-wrap gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => handleRepairSingleAndNext(true)}
                      disabled={refittingSingle || loadingWaveform}
                      className="btn-primary flex-1"
                    >
                      {refittingSingle ? (
                        <RefreshCw className="w-5 h-5 animate-spin" />
                      ) : (
                        <Wrench className="w-5 h-5" />
                      )}
                      <span>この num を個別再フィットして次の選択項目へ ▶</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleApplyCurrentParamsToSelectedInGroup}
                      disabled={refittingBatch}
                      className="btn-secondary"
                      title="同じピークグループ内でチェックされているすべての num にこの設定を適用して一括フィットします"
                    >
                      <Layers className="w-4 h-4 text-cyan-400" />
                      <span>同グループの選択中 num すべてにこの設定を一括適用</span>
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-12 text-center text-zinc-400">
                左のリストからフレームを選択するか、任意の `num` を追加してください。
              </div>
            )}
          </div>
        </div>
      )}

      {/* =====================================================================
          SUB-SCREEN 4-B: Parameter Trend Charts & Unified Data Table
         ===================================================================== */}
      {subScreen === 'trend_and_export' && (
        <div className="space-y-6">
          {/* Group Selector Pills */}
          <div className="panel-card p-4 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-bold text-zinc-300 mr-2">表示ピークグループ:</span>
              {groupIds.map((gid) => {
                const grp = batchResults[gid];
                if (!grp) return null;
                const isSelected = activeTrendGroupId === gid;
                return (
                  <button
                    key={gid}
                    type="button"
                    onClick={() => setActiveTrendGroupId(gid)}
                    className={`px-4 py-2 rounded-lg text-sm font-mono font-semibold transition-all ${
                      isSelected
                        ? 'bg-cyan-500 text-zinc-950 shadow'
                        : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700'
                    }`}
                  >
                    {grp.peaks.join(' + ')}
                    {grp.outlier_nums && grp.outlier_nums.length > 0 && (
                      <span className="ml-2 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 text-xs">
                        要確認 {grp.outlier_nums.length}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <span className="text-xs sm:text-sm text-zinc-400">
              ※グラフ上の点をクリックすると「① 個別フィット修復画面」でそのフレームを開きます
            </span>
          </div>

          {activeTrendGroup && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <div className="panel-card p-4">
                <h4 className="text-base font-bold text-zinc-100 mb-2">
                  回折角 2θ (deg) の連続推移
                </h4>
                <PlotlyChart
                  data={trendTraces.twoTh}
                  layout={{
                    xaxis: { title: 'num' },
                    yaxis: { title: '2θ (deg)' },
                  }}
                  onPointClick={(pt) => {
                    const num = Math.round(pt.x);
                    const key = `${activeTrendGroupId}::${num}`;
                    setCustomAddedItems((prev) =>
                      prev.some((p) => p.key === key)
                        ? prev
                        : [
                            ...prev,
                            {
                              key,
                              group_id: activeTrendGroupId,
                              sheet_name: activeTrendGroup.sheet_name,
                              peaks: activeTrendGroup.peaks,
                              phaseLabel: 'グラフから選択',
                              hasGamma: true,
                              hasAlpha: true,
                              num,
                              isFlaggedOutlier: false,
                            },
                          ]
                    );
                    setSelectedKeys((prev) => ({ ...prev, [key]: true }));
                    loadWaveformForItem(activeTrendGroupId, num);
                    setSubScreen('outlier_studio');
                  }}
                  className="w-full h-72"
                />
              </div>

              <div className="panel-card p-4">
                <h4 className="text-base font-bold text-zinc-100 mb-2">
                  積分強度 I (Area A) の連続推移
                </h4>
                <PlotlyChart
                  data={trendTraces.area}
                  layout={{
                    xaxis: { title: 'num' },
                    yaxis: { title: '積分強度 I (a.u.)' },
                  }}
                  onPointClick={(pt) => {
                    const num = Math.round(pt.x);
                    loadWaveformForItem(activeTrendGroupId, num);
                    setSubScreen('outlier_studio');
                  }}
                  className="w-full h-72"
                />
              </div>

              <div className="panel-card p-4">
                <h4 className="text-base font-bold text-zinc-100 mb-2">
                  合成半値幅 FWHM (deg) の連続推移
                </h4>
                <PlotlyChart
                  data={trendTraces.fwhm}
                  layout={{
                    xaxis: { title: 'num' },
                    yaxis: { title: 'FWHM (deg)' },
                  }}
                  onPointClick={(pt) => {
                    const num = Math.round(pt.x);
                    loadWaveformForItem(activeTrendGroupId, num);
                    setSubScreen('outlier_studio');
                  }}
                  className="w-full h-72"
                />
              </div>

              <div className="panel-card p-4 lg:col-span-3">
                <h4 className="text-base font-bold text-zinc-100 mb-2">
                  フレームごとの相対残差 `residual` の連続推移（クリックで個別フィット修復へ）
                </h4>
                <PlotlyChart
                  data={trendTraces.residual}
                  layout={{
                    xaxis: { title: 'num' },
                    yaxis: { title: 'Relative Residual (residual)' },
                  }}
                  onPointClick={(pt) => {
                    const num = Math.round(pt.x);
                    loadWaveformForItem(activeTrendGroupId, num);
                    setSubScreen('outlier_studio');
                  }}
                  className="w-full h-56"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
