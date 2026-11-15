import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Layers,
  TrendingUp,
  RefreshCw,
  FolderOpen,
  FileSpreadsheet,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Compass,
  Sliders,
} from 'lucide-react';
import { PlotlyChart } from './PlotlyChart';
import { TutorialGuideBanner } from './TutorialGuideBanner';
import { apiPost, fmtFixed, fmtSci } from '../lib/utils';
import type { BatchGroupResult, PhysicsAnalysisResponse } from '../types/xrd';

export interface Step5PhysicsAnalysisProps {
  folderPath: string;
  specimenName: string;
  batchResults: Record<string, BatchGroupResult>;
}

type PhysicsSubView = 'phase_fraction' | 'dislocation' | 'lattice_strain' | 'table';

export const Step5PhysicsAnalysis: React.FC<Step5PhysicsAnalysisProps> = ({
  folderPath,
  specimenName,
  batchResults,
}) => {
  const [activeSubView, setActiveSubView] = useState<PhysicsSubView>('phase_fraction');
  const [excelPath, setExcelPath] = useState<string>('');
  const [instrumentalFwhm, setInstrumentalFwhm] = useState<number>(0.018);
  const [aGamma0, setAGamma0] = useState<number>(0.3595);
  const [aAlpha0, setAAlpha0] = useState<number>(0.2868);
  const [showAdvancedParams, setShowAdvancedParams] = useState<boolean>(false);

  const [physicsData, setPhysicsData] = useState<PhysicsAnalysisResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const runAnalysis = useCallback(
    async (overrideExcelPath?: string) => {
      setLoading(true);
      setErrorMsg(null);
      try {
        const targetExcel = (overrideExcelPath ?? excelPath).trim();
        const hasSessionGroups = Object.keys(batchResults).length > 0;
        const payload: Record<string, unknown> = {
          folder_path: folderPath || undefined,
          specimen_name: specimenName || undefined,
          excel_path: targetExcel || undefined,
          groups: !targetExcel && hasSessionGroups ? batchResults : undefined,
          instrumental_fwhm_deg: instrumentalFwhm,
          a_gamma0_nm: aGamma0,
          a_alpha0_nm: aAlpha0,
        };
        const res = await apiPost<PhysicsAnalysisResponse>(
          '/api/fitting/physics-analysis',
          payload
        );
        setPhysicsData(res);
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [folderPath, specimenName, batchResults, excelPath, instrumentalFwhm, aGamma0, aAlpha0]
  );

  useEffect(() => {
    if (Object.keys(batchResults).length > 0 || folderPath) {
      runAnalysis();
    }
  }, [batchResults, folderPath]);

  const handleBrowseExcel = async () => {
    try {
      const res = await apiPost<{ selected_path: string; cancelled: boolean }>(
        '/api/dialog/select',
        {
          mode: 'excel_file',
          title: '解析済みの output.xlsx ファイルを選択',
          initial_dir: folderPath || undefined,
        }
      );
      if (!res.cancelled && res.selected_path) {
        setExcelPath(res.selected_path);
        await runAnalysis(res.selected_path);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  };

  // --- Summary KPIs ---
  const kpiStats = useMemo(() => {
    if (!physicsData || physicsData.nums.length === 0) return null;
    const maxFAlpha = Math.max(...physicsData.f_alpha_prime);
    const finalFAlpha = physicsData.f_alpha_prime[physicsData.f_alpha_prime.length - 1] ?? 0;

    const validRhoG = physicsData.rho_gamma_m2.filter(
      (v): v is number => v !== null && !Number.isNaN(v)
    );
    const validRhoA = physicsData.rho_alpha_prime_m2.filter(
      (v): v is number => v !== null && !Number.isNaN(v)
    );

    const maxRhoG = validRhoG.length > 0 ? Math.max(...validRhoG) : null;
    const maxRhoA = validRhoA.length > 0 ? Math.max(...validRhoA) : null;

    return {
      maxFAlpha,
      finalFAlpha,
      maxRhoG,
      maxRhoA,
      onsetNum: physicsData.kinetics_fit?.onset_num ?? null,
    };
  }, [physicsData]);

  // --- Plot 1: Martensite & Austenite Phase Fraction + Olson-Cohen Kinetics ---
  const phaseFractionTraces = useMemo(() => {
    if (!physicsData) return [];
    const traces: Record<string, unknown>[] = [
      {
        x: physicsData.nums,
        y: physicsData.f_gamma.map((v) => v * 100),
        type: 'scatter',
        mode: 'lines+markers',
        name: 'オーステナイト相分率 f_γ (%)',
        line: { color: '#06B6D4', width: 2.5 },
        marker: { size: 6, color: '#06B6D4' },
      },
      {
        x: physicsData.nums,
        y: physicsData.f_alpha_prime.map((v) => v * 100),
        type: 'scatter',
        mode: 'lines+markers',
        name: 'マルテンサイト相分率 f_α\' (%)',
        line: { color: '#F59E0B', width: 3 },
        marker: { size: 7, symbol: 'diamond', color: '#F59E0B' },
      },
    ];

    if (physicsData.kinetics_fit?.fitted_curve) {
      traces.push({
        x: physicsData.nums,
        y: physicsData.kinetics_fit.fitted_curve.map((v) => v * 100),
        type: 'scatter',
        mode: 'lines',
        name: `Olson-Cohen型 変態速度式フィット (n=${fmtFixed(physicsData.kinetics_fit.n, 2)})`,
        line: { color: '#EF4444', width: 2.5, dash: 'dash' },
      });
    }
    return traces;
  }, [physicsData]);

  // --- Plot 2: Dislocation Density per Phase & per Peak ---
  const dislocationTraces = useMemo(() => {
    if (!physicsData) return [];
    const traces: Record<string, unknown>[] = [];

    if (physicsData.rho_gamma_m2.some((v) => v !== null)) {
      traces.push({
        x: physicsData.nums,
        y: physicsData.rho_gamma_m2,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'γ-FCC相 平均転位密度 ρ_γ (m⁻²)',
        line: { color: '#06B6D4', width: 3 },
        marker: { size: 7, color: '#06B6D4' },
      });
    }

    if (physicsData.rho_alpha_prime_m2.some((v) => v !== null)) {
      traces.push({
        x: physicsData.nums,
        y: physicsData.rho_alpha_prime_m2,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'α\'-BCC相 平均転位密度 ρ_α\' (m⁻²)',
        line: { color: '#F59E0B', width: 3 },
        marker: { size: 7, symbol: 'diamond', color: '#F59E0B' },
      });
    }

    // Add individual reflection dislocation densities as subtle dashed traces
    const palette = ['#38BDF8', '#818CF8', '#34D399', '#FBBF24', '#FB923C', '#F472B6'];
    let cIdx = 0;
    for (const [pk, vals] of Object.entries(physicsData.dislocation_by_peak_m2)) {
      if (vals.some((v) => v !== null)) {
        traces.push({
          x: physicsData.nums,
          y: vals,
          type: 'scatter',
          mode: 'lines',
          name: `面指数別 ρ (${pk})`,
          line: {
            color: palette[cIdx % palette.length],
            width: 1.5,
            dash: 'dot',
          },
          opacity: 0.75,
        });
        cIdx += 1;
      }
    }
    return traces;
  }, [physicsData]);

  // --- Plot 3: Elastic Lattice Strain & Lattice Constants ---
  const latticeStrainTraces = useMemo(() => {
    if (!physicsData) return [];
    const traces: Record<string, unknown>[] = [];
    const gammaColors = ['#06B6D4', '#38BDF8', '#22D3EE', '#67E8F9', '#0284C7'];
    const alphaColors = ['#F59E0B', '#FB923C', '#FBBF24', '#F97316'];
    let gIdx = 0;
    let aIdx = 0;

    for (const [pk, vals] of Object.entries(physicsData.lattice_strains_ue)) {
      if (!vals.some((v) => v !== null)) continue;
      const isFcc = pk.toLowerCase().startsWith('fcc');
      const color = isFcc
        ? gammaColors[gIdx++ % gammaColors.length]
        : alphaColors[aIdx++ % alphaColors.length];

      traces.push({
        x: physicsData.nums,
        y: vals,
        type: 'scatter',
        mode: 'lines+markers',
        name: `${isFcc ? 'γ-FCC' : "α'-BCC"} ${pk} 弾性格子ひずみ (με)`,
        line: { color, width: 2.2 },
        marker: { size: 5, symbol: isFcc ? 'circle' : 'diamond', color },
      });
    }
    return traces;
  }, [physicsData]);

  const latticeConstantTraces = useMemo(() => {
    if (!physicsData) return [];
    const traces: Record<string, unknown>[] = [];
    if (physicsData.a_gamma_nm.some((v) => v !== null)) {
      traces.push({
        x: physicsData.nums,
        y: physicsData.a_gamma_nm,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'γ-FCC 格子定数 a_γ (nm)',
        line: { color: '#06B6D4', width: 2.5 },
        marker: { size: 6, color: '#06B6D4' },
      });
    }
    if (physicsData.a_alpha_prime_nm.some((v) => v !== null)) {
      traces.push({
        x: physicsData.nums,
        y: physicsData.a_alpha_prime_nm,
        type: 'scatter',
        mode: 'lines+markers',
        name: "α'-BCC 格子定数 a_α' (nm)",
        yaxis: 'y2',
        line: { color: '#F59E0B', width: 2.5 },
        marker: { size: 6, symbol: 'diamond', color: '#F59E0B' },
      });
    }
    return traces;
  }, [physicsData]);

  return (
    <div className="space-y-6">
      {/* Tutorial Guide Banner */}
      <TutorialGuideBanner
        mode="xrd"
        stepTitle="Step 5: 材料組織・物理量解析スタジオ（マルテンサイト相分率・各相転位密度・格子ひずみ）"
        summary="フィッティングで得られた回折角 (2θ)・積分強度 (I)・半値幅 (FWHM) から、準安定オーステナイト鋼の相変態挙動と転位密度進化を自動計算して可視化します。"
        steps={[
          {
            badge: '手順 1',
            title: '自動で物理量を算出（または既存の output.xlsx を読込）',
            description:
              'Step 3〜4 のフィッティング結果から自動的に計算されます。過去に保存した output.xlsx を読み込んでグラフ化することも可能です。',
          },
          {
            badge: '手順 2',
            title: '画面切替タブで見たい物理グラフを選択',
            description:
              '「① マルテンサイト相分率」「② 各相の転位密度変化」「③ 弾性格子ひずみ・格子定数」「④ 物理量データ表」をワンクリックで切り替えられます。',
          },
          {
            badge: '手順 3',
            title: 'output.xlsx の Physical_Analysis シートにも自動保存',
            description:
              'Step 4でExcel出力を実行すると、これらの計算結果と物理グラフ画像も「Physical_Analysis」シートに自動で書き出されます。',
          },
        ]}
        glossary={[
          {
            term: 'マルテンサイト相分率 (Direct Comparison法)',
            meaning:
              '各回折ピークの積分強度 I_hkl を多重度・構造因子 |F|²・ローレンツ偏光因子 LP(θ) で規格化し、γ-FCC相とα\'-BCC相の体積分率を算出します。',
          },
          {
            term: '各相の転位密度 ρ (Modified Williamson-Hall / Williamson-Smallman法)',
            meaning:
              '回折ピークの物理的広がり（FWHMから装置幅を除去した値）と異方性転位コントラスト因子 C_hkl、バーガースベクトル b から γ相・α\'相それぞれの転位密度 (m⁻²) を算出します。',
          },
        ]}
        tip="複数の回折ピーク（例：fcc111+bcc110 ペア、fcc200、bcc211 など）をフィッティングしておくほど、相分率や転位密度の算出精度がさらに向上します。"
      />

      {/* Data Source & Controls Bar */}
      <div data-tour="step5-params-bar" className="panel-card p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center text-cyan-300">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-zinc-100">
                物理量解析データソース ＆ 結晶学パラメータ
              </h3>
              <p className="text-sm text-zinc-300">
                現在の解析セッション、または任意の <code className="text-cyan-300">*output.xlsx</code> ファイルから即座にグラフを生成できます
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => setShowAdvancedParams((prev) => !prev)}
              className="btn-secondary"
            >
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>物理定数・装置幅の設定</span>
            </button>
            <button
              type="button"
              onClick={handleBrowseExcel}
              className="btn-secondary"
            >
              <FolderOpen className="w-4 h-4 text-amber-400" />
              <span>既存の output.xlsx を開く</span>
            </button>
            <button
              type="button"
              onClick={() => runAnalysis()}
              disabled={loading}
              className="btn-primary"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>物理量を再計算</span>
            </button>
          </div>
        </div>

        {excelPath && (
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-lg bg-zinc-950 border border-amber-500/40 text-sm">
            <div className="flex items-center gap-2 font-mono text-amber-200 truncate">
              <FileSpreadsheet className="w-4 h-4 text-amber-400 shrink-0" />
              <span>読込中のExcel: {excelPath}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                setExcelPath('');
                runAnalysis('');
              }}
              className="text-xs text-zinc-300 hover:text-white underline shrink-0"
            >
              現在のセッション結果に戻す
            </button>
          </div>
        )}

        {showAdvancedParams && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-3 border-t border-zinc-800">
            <div>
              <label className="label-sm block mb-1.5">
                装置半値幅 `FWHM_inst` (deg)
              </label>
              <input
                type="number"
                step="0.002"
                min="0.002"
                max="0.1"
                value={instrumentalFwhm}
                onChange={(e) => setInstrumentalFwhm(parseFloat(e.target.value) || 0.018)}
                className="input-field font-mono tabular-nums"
              />
            </div>
            <div>
              <label className="label-sm block mb-1.5">
                初期γ相 基準格子定数 `a_γ0` (nm)
              </label>
              <input
                type="number"
                step="0.0005"
                value={aGamma0}
                onChange={(e) => setAGamma0(parseFloat(e.target.value) || 0.3595)}
                className="input-field font-mono tabular-nums"
              />
            </div>
            <div>
              <label className="label-sm block mb-1.5">
                初期α&apos;相 基準格子定数 `a_α'0` (nm)
              </label>
              <input
                type="number"
                step="0.0005"
                value={aAlpha0}
                onChange={(e) => setAAlpha0(parseFloat(e.target.value) || 0.2868)}
                className="input-field font-mono tabular-nums"
              />
            </div>
          </div>
        )}

        {errorMsg && (
          <div className="p-4 rounded-xl bg-red-950/60 border border-red-500/40 text-sm text-red-200 flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* KPI Cards */}
      {physicsData && kpiStats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="panel-card p-4 border-amber-500/30">
            <div className="text-sm font-medium text-amber-300">
              最大マルテンサイト相分率 (f_α&apos;)
            </div>
            <div className="mt-1.5 text-3xl font-bold font-mono tabular-nums text-amber-300">
              {fmtFixed(kpiStats.maxFAlpha * 100, 1)}%
            </div>
            <div className="mt-1 text-xs text-zinc-400 font-mono tabular-nums">
              最終フレーム時: {fmtFixed(kpiStats.finalFAlpha * 100, 1)}%
              {kpiStats.onsetNum !== null && ` / 変態開始 num≈#${fmtFixed(kpiStats.onsetNum, 0)}`}
            </div>
          </div>

          <div className="panel-card p-4 border-cyan-500/30">
            <div className="text-sm font-medium text-cyan-300">
              γ-FCC相 最大転位密度 (ρ_γ)
            </div>
            <div className="mt-1.5 text-3xl font-bold font-mono tabular-nums text-cyan-300">
              {fmtSci(kpiStats.maxRhoG, 2)}{' '}
              <span className="text-sm font-normal text-zinc-400">m⁻²</span>
            </div>
            <div className="mt-1 text-xs text-zinc-400">
              解析ピーク: {physicsData.gamma_peaks.join(', ') || 'なし'}
            </div>
          </div>

          <div className="panel-card p-4 border-orange-500/30">
            <div className="text-sm font-medium text-orange-300">
              α&apos;-BCC相 最大転位密度 (ρ_α&apos;)
            </div>
            <div className="mt-1.5 text-3xl font-bold font-mono tabular-nums text-orange-300">
              {fmtSci(kpiStats.maxRhoA, 2)}{' '}
              <span className="text-sm font-normal text-zinc-400">m⁻²</span>
            </div>
            <div className="mt-1 text-xs text-zinc-400">
              解析ピーク: {physicsData.alpha_prime_peaks.join(', ') || 'γ強度減衰から推定'}
            </div>
          </div>

          <div className="panel-card p-4">
            <div className="text-sm font-medium text-zinc-300">
              放射光X線波長 λ (自動較正)
            </div>
            <div className="mt-1.5 text-2xl font-bold font-mono tabular-nums text-zinc-100">
              {fmtFixed(physicsData.wavelength_nm, 5)}{' '}
              <span className="text-sm font-normal text-zinc-400">nm</span>
            </div>
            <div className="mt-1 text-xs font-mono tabular-nums text-emerald-400">
              相当エネルギー: E ≈ {fmtFixed(physicsData.energy_kev, 2)} keV
            </div>
          </div>
        </div>
      )}

      {/* Sub-Screen Navigation Tabs (Clean Screen Transition) */}
      <div data-tour="step5-graph-tabs" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          {
            id: 'phase_fraction' as PhysicsSubView,
            title: '① マルテンサイト相分率の変化',
            subtitle: 'f_α\' / f_γ 推移 ＋ Olson-Cohen速度式',
            accent: 'cyan',
          },
          {
            id: 'dislocation' as PhysicsSubView,
            title: '② 各相の転位密度変化 (ρ_γ, ρ_α\')',
            subtitle: 'オーステナイト相・マルテンサイト相の転位蓄積',
            accent: 'amber',
          },
          {
            id: 'lattice_strain' as PhysicsSubView,
            title: '③ 弾性格子ひずみ・格子定数変化',
            subtitle: '面指数別ひずみ分配 ε_hkl と格子定数 a',
            accent: 'emerald',
          },
          {
            id: 'table' as PhysicsSubView,
            title: '④ 算出物理量データ一覧表',
            subtitle: '全フレーム (num) の相分率・転位密度数値表',
            accent: 'cyan',
          },
        ].map((tab) => {
          const isCurrent = activeSubView === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveSubView(tab.id)}
              className={`p-4 rounded-xl border text-left transition-all ${
                isCurrent
                  ? 'bg-zinc-800/95 border-cyan-400 shadow-md shadow-cyan-500/10'
                  : 'bg-zinc-900/60 border-zinc-800 hover:bg-zinc-800/60 hover:border-zinc-700'
              }`}
            >
              <div className="text-base font-bold text-zinc-100">{tab.title}</div>
              <div className="text-xs sm:text-sm text-zinc-400 mt-0.5">{tab.subtitle}</div>
            </button>
          );
        })}
      </div>

      {/* Focused Full-Screen Graph View */}
      {physicsData ? (
        <div className="panel-card p-6 space-y-5">
          {activeSubView === 'phase_fraction' && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-xl font-bold text-zinc-100">
                    マルテンサイト相分率 (f_α&apos;) ＆ オーステナイト相分率 (f_γ) の連続変化
                  </h3>
                  <p className="text-sm text-zinc-300">
                    加工誘起マルテンサイト変態（DIMT）に伴う二相組織分率の推移とOlson-Cohenカイネティクス回帰曲線
                  </p>
                </div>
                {physicsData.kinetics_fit && (
                  <div className="px-4 py-2 rounded-lg bg-zinc-950 border border-zinc-800 text-sm font-mono tabular-nums text-zinc-200">
                    Olson-Cohen パラメータ: f_s={fmtFixed(physicsData.kinetics_fit.fs, 3)}, β=
                    {fmtSci(physicsData.kinetics_fit.beta, 2)}, n=
                    {fmtFixed(physicsData.kinetics_fit.n, 2)}, 開始num=#
                    {fmtFixed(physicsData.kinetics_fit.onset_num, 0)}
                  </div>
                )}
              </div>

              <PlotlyChart
                data={phaseFractionTraces}
                layout={{
                  xaxis: { title: 'ファイル番号 num (引張変形ステップ)' },
                  yaxis: { title: '相体積分率 Volume Fraction (%)', range: [-2, 105] },
                }}
                className="w-full h-[500px]"
              />
            </div>
          )}

          {activeSubView === 'dislocation' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-bold text-zinc-100">
                  各相（γ-FCC相・α&apos;-BCC相）および各結晶面の転位密度変化
                </h3>
                <p className="text-sm text-zinc-300">
                  回折ピークの半値幅（FWHM）と結晶異方性コントラスト因子 C_hkl から算出した転位密度 ρ (m⁻²) の対数プロット
                </p>
              </div>

              <PlotlyChart
                data={dislocationTraces}
                layout={{
                  xaxis: { title: 'ファイル番号 num (引張変形ステップ)' },
                  yaxis: {
                    title: '転位密度 Dislocation Density ρ (m⁻²)',
                    type: 'log',
                    exponentformat: 'power',
                  },
                }}
                className="w-full h-[500px]"
              />
            </div>
          )}

          {activeSubView === 'lattice_strain' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-zinc-100">
                  面指数別 弾性格子ひずみ変化 (ε_hkl) と各相への応力分配挙動
                </h3>
                <p className="text-sm text-zinc-300">
                  変形初期の面間隔 d_0 からの変化率 ε_hkl = (d - d_0)/d_0 × 10⁶ [με]。リューダース変形やマルテンサイト変態開始時の荷重分配が確認できます。
                </p>
              </div>

              <PlotlyChart
                data={latticeStrainTraces}
                layout={{
                  xaxis: { title: 'ファイル番号 num (引張変形ステップ)' },
                  yaxis: { title: '弾性格子ひずみ Elastic Lattice Strain ε_hkl (με)' },
                }}
                className="w-full h-[440px]"
              />

              <div className="pt-4 border-t border-zinc-800">
                <h4 className="text-lg font-bold text-zinc-100 mb-2">
                  γ-FCC相 および α&apos;-BCC相の平均格子定数 (nm) の推移
                </h4>
                <PlotlyChart
                  data={latticeConstantTraces}
                  layout={{
                    xaxis: { title: 'ファイル番号 num' },
                    yaxis: { title: 'γ-FCC 格子定数 a_γ (nm)' },
                    yaxis2: {
                      title: "α'-BCC 格子定数 a_α' (nm)",
                      overlaying: 'y',
                      side: 'right',
                      gridcolor: 'rgba(0,0,0,0)',
                    },
                  }}
                  className="w-full h-[360px]"
                />
              </div>
            </div>
          )}

          {activeSubView === 'table' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-bold text-zinc-100">
                  全フレーム 物理量算出テーブル（相分率・転位密度・格子定数）
                </h3>
                <span className="text-sm font-mono tabular-nums text-zinc-400">
                  全 {physicsData.summary_rows.length} フレーム
                </span>
              </div>

              <div className="overflow-x-auto max-h-[520px] border border-zinc-800 rounded-xl">
                <table className="w-full text-left border-collapse text-sm">
                  <thead className="sticky top-0 bg-zinc-900 border-b border-zinc-700 text-zinc-200">
                    <tr>
                      <th className="py-3 px-4 font-semibold">num</th>
                      <th className="py-3 px-4 font-semibold text-right text-cyan-300">
                        f_γ (%)
                      </th>
                      <th className="py-3 px-4 font-semibold text-right text-amber-300">
                        f_α&apos; (%)
                      </th>
                      <th className="py-3 px-4 font-semibold text-right text-cyan-300">
                        ρ_γ (m⁻²)
                      </th>
                      <th className="py-3 px-4 font-semibold text-right text-amber-300">
                        ρ_α&apos; (m⁻²)
                      </th>
                      <th className="py-3 px-4 font-semibold text-right">
                        a_γ (nm)
                      </th>
                      <th className="py-3 px-4 font-semibold text-right">
                        a_α&apos; (nm)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/70 font-mono tabular-nums">
                    {physicsData.summary_rows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-zinc-800/40">
                        <td className="py-2.5 px-4 font-bold text-zinc-100">#{row.num}</td>
                        <td className="py-2.5 px-4 text-right text-cyan-300">
                          {fmtFixed(Number(row.f_gamma ?? 0) * 100, 2)}%
                        </td>
                        <td className="py-2.5 px-4 text-right text-amber-300 font-semibold">
                          {fmtFixed(Number(row.f_alpha_prime ?? 0) * 100, 2)}%
                        </td>
                        <td className="py-2.5 px-4 text-right text-zinc-200">
                          {fmtSci(row.rho_gamma_m2 as number | null, 2)}
                        </td>
                        <td className="py-2.5 px-4 text-right text-zinc-200">
                          {fmtSci(row.rho_alpha_prime_m2 as number | null, 2)}
                        </td>
                        <td className="py-2.5 px-4 text-right text-zinc-300">
                          {fmtFixed(row.a_gamma_nm as number | null, 5)}
                        </td>
                        <td className="py-2.5 px-4 text-right text-zinc-300">
                          {fmtFixed(row.a_alpha_prime_nm as number | null, 5)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="panel-card p-12 text-center space-y-3">
          <Sparkles className="w-10 h-10 text-cyan-400 mx-auto" />
          <div className="text-lg font-bold text-zinc-200">
            Step 3 で連続フィッティングを実行するか、既存の output.xlsx を選択してください
          </div>
          <p className="text-sm text-zinc-400 max-w-xl mx-auto">
            フィッティング結果が揃うと、ここにマルテンサイト相分率 (f_α&apos;)、各相の転位密度 (ρ_γ, ρ_α&apos;)、および弾性格子ひずみ (ε_hkl) のグラフが自動で表示されます。
          </p>
        </div>
      )}
    </div>
  );
};
