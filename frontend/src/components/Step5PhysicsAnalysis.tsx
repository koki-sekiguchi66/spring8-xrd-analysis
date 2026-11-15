import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
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
import { EmptyCanvas } from './ui/EmptyCanvas';
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
  onPhysicsComputed?: () => void;
}

type PhysicsSubView = 'phase_fraction' | 'dislocation' | 'lattice_strain' | 'table';

const PEAK_COLORS = ['#38bdf8', '#f59e0b', '#34d399', '#a78bfa', '#f472b6', '#fb7185'];

export const Step5PhysicsAnalysis: React.FC<Step5PhysicsAnalysisProps> = ({
  folderPath,
  specimenName,
  batchResults,
  onPhysicsComputed,
}) => {
  const [activeSubView, setActiveSubView] = useState<PhysicsSubView>('phase_fraction');
  const [excelPath, setExcelPath] = useState<string>('');
  const [instrumentalFwhm, setInstrumentalFwhm] = useState<number>(0.018);
  const [wavelengthNm, setWavelengthNm] = useState<number>(0.04133);
  const [aGamma0, setAGamma0] = useState<number>(0.3588);
  const [aAlpha0, setAAlpha0] = useState<number>(0.2905);
  // '' = DIMT onset stored with the fitted groups; 0 = disabled
  const [zeroAlphaBefore, setZeroAlphaBefore] = useState<string>('');
  const [excludedRefl, setExcludedRefl] = useState<string[]>([]);
  const [bIso, setBIso] = useState<number>(0.35);
  const [rLattice, setRLattice] = useState<'measured' | 'reference'>('measured');
  // '' = all frames; e.g. exclude frames after fracture
  const [maxNum, setMaxNum] = useState<string>('');
  const [showAdvancedParams, setShowAdvancedParams] = useState<boolean>(false);

  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<PhysicsAnalysisResponse | null>(null);

  const hasSessionGroups = Object.keys(batchResults).length > 0;

  const handleBrowseExcel = async () => {
    try {
      const res = await apiPost<{ selected_path?: string; path?: string; cancelled?: boolean }>(
        '/api/dialog/select',
        {
          mode: 'excel_file',
          title: 'Excel 選択',
          initial_dir: folderPath || undefined,
        }
      );
      const picked = res.selected_path || res.path;
      if (!res.cancelled && picked) {
        setExcelPath(picked);
      }
    } catch (e: any) {
      setErrorMsg(e.message || '選択エラー');
    }
  };

  const handleRunAnalysis = async (
    overrideExcel?: string,
    overrideExcluded?: string[],
    overrideMaxNum?: string
  ) => {
    const targetExcel = (overrideExcel !== undefined ? overrideExcel : excelPath).trim();
    if (!targetExcel && !hasSessionGroups && !folderPath) {
      setErrorMsg('対象データ未指定 (Step 3 実行または output.xlsx 指定が必要)');
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
        b_iso_A2: bIso,
        r_lattice: rLattice,
        max_num: (() => {
          const v = (overrideMaxNum ?? maxNum).trim();
          return v === '' ? undefined : Number(v);
        })(),
      });
      setResult(res);
      onPhysicsComputed?.();
    } catch (e: any) {
      setErrorMsg(e.message || '計算エラー');
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
        name: `経験式 f(num) (n=${fmtFixed(result.kinetics_fit.n, 2)})`,
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
        name: '平均 ρ_γ',
        line: { color: '#38bdf8', width: 2 },
        marker: { size: 5, color: '#38bdf8' },
      },
      {
        x: xs,
        y: result.rho_alpha_prime_m2,
        type: 'scatter',
        mode: 'lines+markers',
        name: "平均 ρ_α'",
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
          name: pk,
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
      {/* Toolbar */}
      <Panel>
        <div className="px-4 py-3 flex flex-wrap items-center justify-between gap-2.5">
          <SegmentedControl<PhysicsSubView>
            ariaLabel="解析ビュー"
            size="md"
            value={activeSubView}
            onChange={setActiveSubView}
            options={[
              { value: 'phase_fraction', label: '相分率', accent: 'amber' },
              { value: 'dislocation', label: '転位密度', accent: 'sky' },
              { value: 'lattice_strain', label: '格子ひずみ', accent: 'emerald' },
              { value: 'table', label: 'テーブル', icon: <TableIcon className="w-4 h-4" /> },
            ]}
          />

          <div className="flex flex-wrap items-center gap-2.5">
            {hasSessionGroups && !excelPath && (
              <StatusBadge tone="emerald" dot>
                セッション読込済み
              </StatusBadge>
            )}
            <div className="flex items-center gap-1.5">
              <div className="w-60">
                <TextInput
                  mono
                  value={excelPath}
                  onChange={(e) => setExcelPath(e.target.value)}
                  placeholder="output.xlsx（任意）"
                />
              </div>
              <Button variant="secondary" size="md" onClick={handleBrowseExcel} title="選択">
                <FolderOpen className="w-4 h-4" />
              </Button>
            </div>
            <Button
              data-guide="step5-calc"
              variant="primary"
              size="md"
              onClick={() => handleRunAnalysis()}
              disabled={isRunning}
            >
              <Play className="w-4 h-4 fill-current" />
              <span>{isRunning ? '計算中...' : '計算'}</span>
            </Button>
          </div>
        </div>
      </Panel>

      {/* Calibration Disclosure */}
      <Disclosure
        title="装置・基準定数"
        summary={`λ ${wavelengthNm}nm · B ${bIso}Å² · R格子 ${rLattice === 'measured' ? '実測' : '基準値'} · 除外 ${excludedRefl.length ? excludedRefl.join(',') : 'なし'}`}
        open={showAdvancedParams}
        onToggle={() => setShowAdvancedParams((v) => !v)}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          <div>
            <FieldLabel>λ</FieldLabel>
            <UnitNumberInput
              unit="nm"
              step="0.00001"
              value={wavelengthNm}
              onChange={(e) => setWavelengthNm(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <FieldLabel>新生 α&apos; = 0 (num &lt;)</FieldLabel>
            <UnitNumberInput
              step="1"
              value={zeroAlphaBefore}
              placeholder={result ? String(result.zero_alpha_before_num ?? '') : '変態開始'}
              onChange={(e) => setZeroAlphaBefore(e.target.value)}
            />
          </div>
          <div>
            <FieldLabel>解析範囲 num ≤</FieldLabel>
            <UnitNumberInput
              step="1"
              value={maxNum}
              placeholder="全フレーム"
              onChange={(e) => setMaxNum(e.target.value)}
            />
          </div>
          <div>
            <FieldLabel>B (Debye-Waller)</FieldLabel>
            <UnitNumberInput
              unit="Å²"
              step="0.01"
              value={bIso}
              onChange={(e) => setBIso(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <FieldLabel>FWHM_inst</FieldLabel>
            <UnitNumberInput
              unit="deg"
              step="0.001"
              value={instrumentalFwhm}
              onChange={(e) => setInstrumentalFwhm(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <FieldLabel>a_γ0</FieldLabel>
            <UnitNumberInput
              unit="nm"
              step="0.0001"
              value={aGamma0}
              onChange={(e) => setAGamma0(parseFloat(e.target.value) || 0)}
            />
          </div>
          <div>
            <FieldLabel>a_α&apos;0</FieldLabel>
            <UnitNumberInput
              unit="nm"
              step="0.0001"
              value={aAlpha0}
              onChange={(e) => setAAlpha0(parseFloat(e.target.value) || 0)}
            />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2.5">
          <FieldLabel>R の格子定数</FieldLabel>
          <SegmentedControl<'measured' | 'reference'>
            ariaLabel="R の格子定数"
            size="sm"
            value={rLattice}
            onChange={setRLattice}
            options={[
              { value: 'measured', label: '実測' },
              { value: 'reference', label: 'a_γ0 / a_α\'0' },
            ]}
          />
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              // Harada's Excel R values: no Debye-Waller term, a_γ = 0.3586 nm, a_α' = 0.2872 nm
              setBIso(0);
              setRLattice('reference');
              setAGamma0(0.3586);
              setAAlpha0(0.2872);
            }}
          >
            原田 Excel 互換
          </Button>
        </div>
        {result?.available_reflections?.length ? (
          <div className="mt-3 space-y-1.5">
            <FieldLabel>相分率に使う反射</FieldLabel>
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
                      {result.R_values?.[key] !== undefined ? ` R=${fmtFixed(result.R_values[key], 1)}` : ''}
                    </span>
                  }
                />
              ))}
            </div>
          </div>
        ) : null}
      </Disclosure>

      {errorMsg && <Notice tone="error">{errorMsg}</Notice>}
      {result?.fracture_num_estimate != null && maxNum.trim() === '' && (
        <Notice tone="warning">
          <span className="tabular-nums">
            num {result.fracture_num_estimate} 以降で全強度が急落 (破断の可能性)。
          </span>{' '}
          <button
            type="button"
            className="underline underline-offset-2 hover:text-amber-100 transition-colors duration-150"
            onClick={() => {
              const v = String((result.fracture_num_estimate ?? 1) - 1);
              setMaxNum(v);
              handleRunAnalysis(undefined, undefined, v);
            }}
          >
            num ≤ {result.fracture_num_estimate - 1} で再計算
          </button>
        </Notice>
      )}

      {/* KPI Strip */}
      <MetricStrip columns={4}>
        <MetricCell
          label="最大 f_α'"
          value={kpiStats.maxAlphaPct !== null ? fmtFixed(kpiStats.maxAlphaPct, 2) : '—'}
          unit="%"
          tone="amber"
          meta={
            result?.kinetics_fit
              ? `fs=${fmtFixed(result.kinetics_fit.fs, 2)} · n=${fmtFixed(result.kinetics_fit.n, 2)}`
              : undefined
          }
        />
        <MetricCell
          label="最大 ρ_γ"
          value={kpiStats.maxRhoGamma !== null ? fmtSci(kpiStats.maxRhoGamma, 2) : '—'}
          unit="m^-2"
          tone="sky"
        />
        <MetricCell
          label="最大 ρ_α'"
          value={kpiStats.maxRhoAlpha !== null ? fmtSci(kpiStats.maxRhoAlpha, 2) : '—'}
          unit="m^-2"
          tone="amber"
        />
        <MetricCell
          label="波長 λ"
          value={result?.wavelength_nm ? fmtFixed(result.wavelength_nm, 5) : '—'}
          unit="nm"
          tone="emerald"
          meta={
            result?.energy_kev
              ? `${fmtFixed(result.energy_kev, 2)} keV${result.wavelength_source === 'default' ? ' (既定)' : ''}`
              : undefined
          }
        />
      </MetricStrip>

      {!result ? (
        <EmptyCanvas
          className="h-64"
          label="計算待機中"
          actionLabel="物性値を計算"
          actionIcon={<Play className="w-3 h-3 fill-current text-sky-400" />}
          onAction={() => handleRunAnalysis()}
        />
      ) : (
        <>
          {activeSubView === 'phase_fraction' && (
            <PlotFrame
              title="相分率推移"
              subtitle="Direct Comparison Method"
              toolbar={
                result.kinetics_fit ? (
                  <StatusBadge tone="emerald" mono>
                    n={fmtFixed(result.kinetics_fit.n, 2)} · β={fmtSci(result.kinetics_fit.beta, 2)}
                  </StatusBadge>
                ) : null
              }
            >
              <PlotlyChart
                data={phaseFractionTraces}
                layout={{
                  xaxis: { title: '#' },
                  yaxis: { title: 'Fraction [%]', range: [0, 105] },
                  margin: { t: 16, r: 16, b: 40, l: 54 },
                }}
                className="w-full h-[420px]"
              />
            </PlotFrame>
          )}

          {activeSubView === 'dislocation' && (
            <PlotFrame
              title="転位密度推移"
              subtitle="Modified Williamson-Hall"
              toolbar={<Activity className="w-3.5 h-3.5 text-sky-400" />}
            >
              <PlotlyChart
                data={dislocationTraces}
                layout={{
                  xaxis: { title: '#' },
                  yaxis: { title: 'ρ [m^-2]', type: 'log' },
                  margin: { t: 16, r: 16, b: 40, l: 62 },
                }}
                className="w-full h-[420px]"
              />
            </PlotFrame>
          )}

          {activeSubView === 'lattice_strain' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <PlotFrame
                title="弾性格子ひずみ (ε)"
                toolbar={<Sliders className="w-3.5 h-3.5 text-emerald-400" />}
              >
                <PlotlyChart
                  data={latticeStrainTraces}
                  layout={{
                    xaxis: { title: '#' },
                    yaxis: { title: 'Strain [με]' },
                    margin: { t: 16, r: 16, b: 40, l: 56 },
                  }}
                  className="w-full h-[380px]"
                />
              </PlotFrame>

              <PlotFrame title="格子定数 (a_γ / a_α')">
                <PlotlyChart
                  data={latticeConstantTraces}
                  layout={{
                    xaxis: { title: '#' },
                    yaxis: { title: 'a_γ [nm]', side: 'left' },
                    yaxis2: {
                      title: "a_α' [nm]",
                      side: 'right',
                      overlaying: 'y',
                      gridcolor: 'transparent',
                    },
                    margin: { t: 16, r: 56, b: 40, l: 56 },
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
                  <thead className="sticky top-0 bg-[#101216] border-b border-[#22262f] text-[#858d9c]">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">#</th>
                      <th className="text-right px-3 py-2 font-medium">f_α&apos; [%]</th>
                      <th className="text-right px-3 py-2 font-medium">f_γ [%]</th>
                      <th className="text-right px-3 py-2 font-medium">ρ_γ [m^-2]</th>
                      <th className="text-right px-3 py-2 font-medium">ρ_α&apos; [m^-2]</th>
                      <th className="text-right px-3 py-2 font-medium">a_γ [nm]</th>
                      <th className="text-right px-3 py-2 font-medium">a_α&apos; [nm]</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1a1d25]">
                    {result.summary_rows.map((row) => (
                      <tr key={String(row.num)} className="hover:bg-[#1c2028] text-[#98a0ae]">
                        <td className="px-3 py-1.5 text-[#eef0f4]">{row.num}</td>
                        <td className="px-3 py-1.5 text-right text-amber-300">
                          {row.f_alpha_prime !== null && row.f_alpha_prime !== undefined
                            ? fmtFixed(row.f_alpha_prime * 100, 2)
                            : '—'}
                        </td>
                        <td className="px-3 py-1.5 text-right text-sky-300">
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
