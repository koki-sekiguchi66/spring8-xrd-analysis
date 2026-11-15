import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Calculator,
  FolderOpen,
  Play,
  Sliders,
  Table as TableIcon,
} from 'lucide-react';
import { BatchGroupResult, PhysicsAnalysisResponse } from '../types/xrd';
import { apiPost, fmtFixed, fmtSci } from '../lib/utils';
import { PlotlyChart } from './PlotlyChart';
import { Button } from './ui/Button';
import { Disclosure } from './ui/Disclosure';
import { CheckboxRow, FieldLabel, TextInput, UnitNumberInput } from './ui/Field';
import { MetricCell, MetricStrip } from './ui/MetricStrip';
import { Notice } from './ui/Notice';
import { Panel } from './ui/Panel';
import { PlotFrame } from './ui/PlotFrame';
import { SegmentedControl } from './ui/SegmentedControl';
import { StatusBadge } from './ui/StatusBadge';

interface Step5PhysicsAnalysisProps {
  folderPath: string;
  specimenName: string;
  batchResults: Record<string, BatchGroupResult>;
}

type PhysicsSubView = 'phase_fraction' | 'dislocation' | 'lattice_strain' | 'table';

const PEAK_COLORS = ['#38bdf8', '#f59e0b', '#34d399', '#a78bfa', '#f472b6', '#fb7185'];

export const Step5PhysicsAnalysis: React.FC<Step5PhysicsAnalysisProps> = ({
  folderPath,
  specimenName,
  batchResults,
}) => {
  const [activeSubView, setActiveSubView] = useState<PhysicsSubView>('phase_fraction');
  const [excelPath, setExcelPath] = useState<string>('');
  const [instrumentalFwhm, setInstrumentalFwhm] = useState<number>(0.018);
  const [wavelengthNm, setWavelengthNm] = useState<number>(0.04133);
  const [aGamma0, setAGamma0] = useState<number>(0.3588);
  const [aAlpha0, setAAlpha0] = useState<number>(0.2905);
  // '' = use the DIMT onset stored with the fitted groups; 0 = disabled
  const [zeroAlphaBefore, setZeroAlphaBefore] = useState<string>('');
  const [excludedRefl, setExcludedRefl] = useState<string[]>([]);
  const [showAdvancedParams, setShowAdvancedParams] = useState<boolean>(false);

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<PhysicsAnalysisResponse | null>(null);

  const hasSessionGroups = Object.keys(batchResults).length > 0;

  const handleBrowseExcel = async () => {
    try {
      const res = await apiPost<{ path?: string }>('/api/dialog/select', {
        mode: 'excel_file',
        title: '解析済みの output.xlsx ファイルを選択',
        initial_dir: folderPath || undefined,
      });
      if (res.path) {
        setExcelPath(res.path);
      }
    } catch (e: any) {
      setErrorMsg(e.message || 'ファイル選択に失敗しました');
    }
  };

  const handleRunAnalysis = async (overrideExcel?: string, overrideExcluded?: string[]) => {
    const targetExcel = (overrideExcel !== undefined ? overrideExcel : excelPath).trim();
    if (!targetExcel && !hasSessionGroups && !folderPath) {
      setErrorMsg('解析対象のデータがありません。Step 3 を実行するか、output.xlsx を指定してください。');
      return;
    }
    setIsRunning(true);
    setErrorMsg(null);
    try {
      const res = await apiPost<PhysicsAnalysisResponse>('/api/fitting/physics-analysis', {
        folder_path: folderPath || undefined,
        specimen_name: specimenName || undefined,
        excel_path: targetExcel || undefined,
        groups: !targetExcel && hasSessionGroups ? batchResults : undefined,
        wavelength_nm: wavelengthNm,
        instrumental_fwhm_deg: instrumentalFwhm,
        a_gamma0_nm: aGamma0,
        a_alpha0_nm: aAlpha0,
        exclude_peaks: overrideExcluded ?? excludedRefl,
        zero_alpha_before_num: zeroAlphaBefore.trim() === '' ? undefined : Number(zeroAlphaBefore),
      });
      setResult(res);
    } catch (e: any) {
      setErrorMsg(e.message || '物理量解析に失敗しました');
    } finally {
      setIsRunning(false);
    }
  };

  useEffect(() => {
    if (hasSessionGroups && !result && !isRunning) {
      handleRunAnalysis('');
    }
  }, [hasSessionGroups]);

  const kpiStats = useMemo(() => {
    if (!result) {
      return {
        maxAlphaPct: null as number | null,
        maxRhoGamma: null as number | null,
        maxRhoAlpha: null as number | null,
      };
    }
    let maxAlphaPct: number | null = null;
    result.f_alpha_prime.forEach((v) => {
      if (typeof v === 'number' && !Number.isNaN(v)) {
        const pct = v * 100;
        if (maxAlphaPct === null || pct > maxAlphaPct) maxAlphaPct = pct;
      }
    });

    let maxRhoGamma: number | null = null;
    result.rho_gamma_m2.forEach((v) => {
      if (typeof v === 'number' && !Number.isNaN(v)) {
        if (maxRhoGamma === null || v > maxRhoGamma) maxRhoGamma = v;
      }
    });

    let maxRhoAlpha: number | null = null;
    result.rho_alpha_prime_m2.forEach((v) => {
      if (typeof v === 'number' && !Number.isNaN(v)) {
        if (maxRhoAlpha === null || v > maxRhoAlpha) maxRhoAlpha = v;
      }
    });

    return { maxAlphaPct, maxRhoGamma, maxRhoAlpha };
  }, [result]);

  const phaseFractionTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!result?.nums?.length) return [];
    const xs = result.nums;
    const traces: Record<string, unknown>[] = [
      {
        x: xs,
        y: result.f_alpha_prime.map((v) => (typeof v === 'number' ? v * 100 : null)),
        type: 'scatter',
        mode: 'lines+markers',
        name: "f_α' [%]",
        line: { color: '#f59e0b', width: 2 },
        marker: { size: 5, color: '#f59e0b' },
      },
      {
        x: xs,
        y: result.f_gamma.map((v) => (typeof v === 'number' ? v * 100 : null)),
        type: 'scatter',
        mode: 'lines+markers',
        name: 'f_γ [%]',
        line: { color: '#38bdf8', width: 2 },
        marker: { size: 5, color: '#38bdf8' },
      },
    ];
    if (result.kinetics_fit?.fitted_curve?.length) {
      traces.push({
        x: xs,
        y: result.kinetics_fit.fitted_curve.map((v) => v * 100),
        type: 'scatter',
        mode: 'lines',
        name: `経験式 f(num) フィット (n=${fmtFixed(result.kinetics_fit.n, 2)})`,
        line: { color: '#34d399', width: 1.8, dash: 'dash' },
      });
    }
    return traces;
  }, [result]);

  const dislocationTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!result?.nums?.length) return [];
    const xs = result.nums;
    const traces: Record<string, unknown>[] = [
      {
        x: xs,
        y: result.rho_gamma_m2,
        type: 'scatter',
        mode: 'lines+markers',
        name: '平均 ρ_γ [m^-2]',
        line: { color: '#38bdf8', width: 2 },
        marker: { size: 5, color: '#38bdf8' },
      },
      {
        x: xs,
        y: result.rho_alpha_prime_m2,
        type: 'scatter',
        mode: 'lines+markers',
        name: "平均 ρ_α' [m^-2]",
        line: { color: '#f59e0b', width: 2 },
        marker: { size: 5, color: '#f59e0b' },
      },
    ];
    if (result.dislocation_by_peak_m2) {
      Object.entries(result.dislocation_by_peak_m2).forEach(([pk, series], idx) => {
        traces.push({
          x: xs,
          y: series,
          type: 'scatter',
          mode: 'lines',
          name: `ρ (${pk})`,
          line: {
            color: PEAK_COLORS[idx % PEAK_COLORS.length],
            width: 1.25,
            dash: 'dot',
          },
        });
      });
    }
    return traces;
  }, [result]);

  const latticeStrainTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!result?.nums?.length || !result.lattice_strains_ue) return [];
    const xs = result.nums;
    return Object.entries(result.lattice_strains_ue).map(([pk, values], idx) => ({
      x: xs,
      y: values,
      type: 'scatter',
      mode: 'lines+markers',
      name: `ε (${pk})`,
      line: { color: PEAK_COLORS[idx % PEAK_COLORS.length], width: 1.75 },
      marker: { size: 4, color: PEAK_COLORS[idx % PEAK_COLORS.length] },
    }));
  }, [result]);

  const latticeConstantTraces = useMemo<Record<string, unknown>[]>(() => {
    if (!result?.nums?.length) return [];
    const xs = result.nums;
    const traces: Record<string, unknown>[] = [];
    if (result.a_gamma_nm?.some((v) => v !== null)) {
      traces.push({
        x: xs,
        y: result.a_gamma_nm,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'a_γ [nm]',
        line: { color: '#38bdf8', width: 2 },
        marker: { size: 4, color: '#38bdf8' },
      });
    }
    if (result.a_alpha_prime_nm?.some((v) => v !== null)) {
      traces.push({
        x: xs,
        y: result.a_alpha_prime_nm,
        type: 'scatter',
        mode: 'lines+markers',
        name: "a_α' [nm]",
        yaxis: 'y2',
        line: { color: '#f59e0b', width: 2 },
        marker: { size: 4, color: '#f59e0b' },
      });
    }
    return traces;
  }, [result]);

  return (
    <div className="space-y-3">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#121418] border border-[#23262e] rounded-md px-3 py-2">
        <SegmentedControl<PhysicsSubView>
          ariaLabel="物理量解析ビュー"
          value={activeSubView}
          onChange={setActiveSubView}
          options={[
            { value: 'phase_fraction', label: "相分率 (f_α', f_γ)", accent: 'amber' },
            { value: 'dislocation', label: '転位密度 (WH / ρ)', accent: 'sky' },
            { value: 'lattice_strain', label: '格子ひずみ・定数', accent: 'emerald' },
            { value: 'table', label: 'データ一覧', icon: <TableIcon className="w-3.5 h-3.5" /> },
          ]}
        />

        <div className="flex flex-wrap items-center gap-2">
          {hasSessionGroups && !excelPath && (
            <StatusBadge tone="emerald" dot>
              セッション結果を直接参照
            </StatusBadge>
          )}
          <div className="flex items-center gap-1.5">
            <div className="w-60">
              <TextInput
                mono
                value={excelPath}
                onChange={(e) => setExcelPath(e.target.value)}
                placeholder="output.xlsx パス（任意）"
              />
            </div>
            <Button variant="secondary" size="sm" onClick={handleBrowseExcel} title="Excelファイルを選択">
              <FolderOpen className="w-3.5 h-3.5" />
            </Button>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleRunAnalysis()}
            disabled={isRunning}
          >
            <Play className="w-3.5 h-3.5" />
            <span>{isRunning ? '計算中...' : '物性値を計算'}</span>
          </Button>
        </div>
      </div>

      {/* Calibration Parameters Disclosure */}
      <Disclosure
        title="物理定数・装置分解能設定"
        summary={`λ=${wavelengthNm}nm · FWHM_inst=${instrumentalFwhm}° · 除外=${excludedRefl.length ? excludedRefl.join(',') : 'なし'}`}
        open={showAdvancedParams}
        onToggle={() => setShowAdvancedParams((v) => !v)}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <FieldLabel hint="ビームタイムの較正値（CeO2 等）">X線波長 λ</FieldLabel>
            <UnitNumberInput
              unit="nm"
              step="0.00001"
              value={wavelengthNm}
              onChange={(e) => setWavelengthNm(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <FieldLabel hint="空欄 = Step 3 の変態開始 num、0 = 無効">新生 α' を 0 とする num 未満</FieldLabel>
            <UnitNumberInput
              step="1"
              value={zeroAlphaBefore}
              placeholder={result ? String(result.zero_alpha_before_num ?? '') : ''}
              onChange={(e) => setZeroAlphaBefore(e.target.value)}
            />
          </div>
          <div>
            <FieldLabel hint="装置由来半値幅（ガウス成分）">装置分解能 FWHM_inst</FieldLabel>
            <UnitNumberInput
              unit="deg"
              step="0.001"
              value={instrumentalFwhm}
              onChange={(e) => setInstrumentalFwhm(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <FieldLabel hint="ピーク位置から測れない場合の予備値">a_γ0</FieldLabel>
            <UnitNumberInput
              unit="nm"
              step="0.0001"
              value={aGamma0}
              onChange={(e) => setAGamma0(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <FieldLabel hint="ピーク位置から測れない場合の予備値">a_α'0</FieldLabel>
            <UnitNumberInput
              unit="nm"
              step="0.0001"
              value={aAlpha0}
              onChange={(e) => setAAlpha0(parseFloat(e.target.value) || 0)}
            />
          </div>
        </div>
        {result?.available_reflections?.length ? (
          <div className="mt-3 space-y-1.5">
            <FieldLabel hint="集合組織の影響が大きい反射（例: fcc111, bcc110）を除外できます">
              相分率に使う反射
            </FieldLabel>
            <div className="flex flex-wrap gap-x-4 gap-y-1.5">
              {result.available_reflections.map((key) => (
                <CheckboxRow
                  key={key}
                  checked={!excludedRefl.includes(key)}
                  onChange={(val) => {
                    const next = val ? excludedRefl.filter((k) => k !== key) : [...excludedRefl, key];
                    setExcludedRefl(next);
                    handleRunAnalysis(undefined, next);
                  }}
                  label={
                    <span className="text-xs font-mono tabular-nums">
                      {key}
                      {result.R_values?.[key] !== undefined ? ` (R=${fmtFixed(result.R_values[key], 1)})` : ''}
                    </span>
                  }
                />
              ))}
            </div>
          </div>
        ) : null}
      </Disclosure>

      {errorMsg && <Notice tone="error">{errorMsg}</Notice>}

      {/* KPI Strip */}
      <MetricStrip columns={4}>
        <MetricCell
          label="最大 α' 相分率"
          value={kpiStats.maxAlphaPct !== null ? fmtFixed(kpiStats.maxAlphaPct, 2) : '—'}
          unit="%"
          tone="amber"
          meta={
            result?.kinetics_fit
              ? `fs=${fmtFixed(result.kinetics_fit.fs, 2)}, n=${fmtFixed(result.kinetics_fit.n, 2)}`
              : undefined
          }
        />
        <MetricCell
          label="最大 γ 転位密度"
          value={kpiStats.maxRhoGamma !== null ? fmtSci(kpiStats.maxRhoGamma, 2) : '—'}
          unit="m^-2"
          tone="sky"
        />
        <MetricCell
          label="最大 α' 転位密度"
          value={kpiStats.maxRhoAlpha !== null ? fmtSci(kpiStats.maxRhoAlpha, 2) : '—'}
          unit="m^-2"
          tone="amber"
        />
        <MetricCell
          label="X線波長 λ"
          value={result?.wavelength_nm ? fmtFixed(result.wavelength_nm, 5) : '—'}
          unit="nm"
          tone="emerald"
          meta={
            result?.energy_kev
              ? `${fmtFixed(result.energy_kev, 2)} keV${result.wavelength_source === 'default' ? '（既定値）' : ''}`
              : undefined
          }
        />
      </MetricStrip>

      {!result ? (
        <Panel className="p-8 text-center">
          <div className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-[#1c1f26] border border-[#23262e] mb-2">
            <Calculator className="w-4 h-4 text-[#38bdf8]" />
          </div>
          <p className="text-[12px] text-[#b4b9c4]">
            「物性値を計算」を実行すると、直接比較法による相分率・修正Williamson-Hall転位密度（半定量）・格子ひずみが算出されます。
          </p>
        </Panel>
      ) : (
        <>
          {activeSubView === 'phase_fraction' && (
            <PlotFrame
              title="マルテンサイト変態相分率 (f_α' / f_γ)"
              subtitle="直接比較法 (Direct Comparison Method)"
              toolbar={
                result.kinetics_fit ? (
                  <StatusBadge tone="emerald" mono>
                    経験式 f(num) n={fmtFixed(result.kinetics_fit.n, 2)} · β={fmtSci(result.kinetics_fit.beta, 2)}
                  </StatusBadge>
                ) : null
              }
            >
              <PlotlyChart
                data={phaseFractionTraces}
                layout={{
                  xaxis: { title: 'フレーム番号' },
                  yaxis: { title: '相分率 [%]', range: [0, 105] },
                  margin: { t: 18, r: 18, b: 46, l: 56 },
                }}
                className="w-full h-[420px]"
              />
            </PlotFrame>
          )}

          {activeSubView === 'dislocation' && (
            <PlotFrame
              title="転位密度推移 (ρ_γ / ρ_α')"
              subtitle="Modified Williamson-Hall / Smallman法"
              toolbar={<Activity className="w-3.5 h-3.5 text-[#38bdf8]" />}
            >
              <PlotlyChart
                data={dislocationTraces}
                layout={{
                  xaxis: { title: 'フレーム番号' },
                  yaxis: { title: '転位密度 ρ [m^-2]', type: 'log' },
                  margin: { t: 18, r: 18, b: 46, l: 64 },
                }}
                className="w-full h-[420px]"
              />
            </PlotFrame>
          )}

          {activeSubView === 'lattice_strain' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <PlotFrame
                title="弾性格子ひずみ推移 (ε)"
                subtitle="基準格子定数からの相対シフト"
                toolbar={<Sliders className="w-3.5 h-3.5 text-[#34d399]" />}
              >
                <PlotlyChart
                  data={latticeStrainTraces}
                  layout={{
                    xaxis: { title: 'フレーム番号' },
                    yaxis: { title: '格子ひずみ [με]' },
                    margin: { t: 18, r: 18, b: 46, l: 58 },
                  }}
                  className="w-full h-[380px]"
                />
              </PlotFrame>

              <PlotFrame
                title="見かけ格子定数推移 (a_γ / a_α')"
                subtitle="Bragg角から逆算"
              >
                <PlotlyChart
                  data={latticeConstantTraces}
                  layout={{
                    xaxis: { title: 'フレーム番号' },
                    yaxis: { title: 'a_γ [nm]', side: 'left' },
                    yaxis2: {
                      title: "a_α' [nm]",
                      side: 'right',
                      overlaying: 'y',
                      gridcolor: 'transparent',
                    },
                    margin: { t: 18, r: 58, b: 46, l: 58 },
                  }}
                  className="w-full h-[380px]"
                />
              </PlotFrame>
            </div>
          )}

          {activeSubView === 'table' && (
            <Panel>
              <div className="max-h-[460px] overflow-auto">
                <table className="w-full text-[11px] font-mono tabular-nums border-collapse">
                  <thead className="sticky top-0 bg-[#121418] border-b border-[#23262e] text-[#787f90]">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">#</th>
                      <th className="text-right px-3 py-2 font-medium">f_α' [%]</th>
                      <th className="text-right px-3 py-2 font-medium">f_γ [%]</th>
                      <th className="text-right px-3 py-2 font-medium">ρ_γ [m^-2]</th>
                      <th className="text-right px-3 py-2 font-medium">ρ_α' [m^-2]</th>
                      <th className="text-right px-3 py-2 font-medium">a_γ [nm]</th>
                      <th className="text-right px-3 py-2 font-medium">a_α' [nm]</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1a1d24]">
                    {result.summary_rows.map((row) => (
                      <tr key={String(row.num)} className="hover:bg-[#1c1f26] text-[#b4b9c4]">
                        <td className="px-3 py-1.5 text-[#eceef2]">{row.num}</td>
                        <td className="px-3 py-1.5 text-right text-[#f59e0b]">
                          {row.f_alpha_prime !== null && row.f_alpha_prime !== undefined
                            ? fmtFixed(row.f_alpha_prime * 100, 2)
                            : '—'}
                        </td>
                        <td className="px-3 py-1.5 text-right text-[#38bdf8]">
                          {row.f_gamma !== null && row.f_gamma !== undefined
                            ? fmtFixed(row.f_gamma * 100, 2)
                            : '—'}
                        </td>
                        <td className="px-3 py-1.5 text-right">{fmtSci(row.rho_gamma_m2, 2)}</td>
                        <td className="px-3 py-1.5 text-right">{fmtSci(row.rho_alpha_prime_m2, 2)}</td>
                        <td className="px-3 py-1.5 text-right">{fmtFixed(row.a_gamma_nm, 5)}</td>
                        <td className="px-3 py-1.5 text-right">{fmtFixed(row.a_alpha_prime_nm, 5)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  );
};
