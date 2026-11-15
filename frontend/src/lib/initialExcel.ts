import type { GroupBatchConfig, PeakFitParam } from '../types/xrd';

/** One initial-value row of a peak block in an Origin / Harada style `_initial.xlsx`. */
export interface InitialEntry {
  No: number | null;
  y0: number;
  xc: number;
  A: number;
  wG: number;
  wL: number;
  FWHM: number;
}

export interface InitialExcelData {
  excel_path: string;
  peaks: Record<string, InitialEntry[]>;
  canonical: Record<string, string | null>;
}

export interface ApplyInitialResult {
  configs: GroupBatchConfig[];
  applied: string[];
  skipped: { group_id: string; reason: string }[];
  warnings: string[];
}

const WG_PER_SIGMA = 2 * Math.sqrt(2 * Math.log(2));

/** fcc111a -> fcc111, bcc112 -> bcc211, bcc101 -> bcc110, bct011 -> bcc110 (indices sorted). */
export function canonicalPeakKey(name: string): string | null {
  const m = /^(fcc|bcc|bct)(\d)(\d)(\d)/i.exec(name.trim());
  if (!m) return null;
  const lattice = m[1].toLowerCase() === 'fcc' ? 'fcc' : 'bcc';
  const hkl = [m[2], m[3], m[4]].map(Number).sort((a, b) => b - a);
  return `${lattice}${hkl.join('')}`;
}

function findEntries(peak: string, cfgPeaks: string[], data: InitialExcelData): InitialEntry[] | null {
  if (data.peaks[peak]?.length) return data.peaks[peak];
  const key = canonicalPeakKey(peak);
  if (!key) return null;
  // Alias match only when it is unambiguous on both sides (e.g. not bcc110a / bcc1102)
  const sameInGroup = cfgPeaks.filter((p) => canonicalPeakKey(p) === key);
  const candidates = Object.keys(data.peaks).filter((n) => (data.canonical[n] ?? canonicalPeakKey(n)) === key);
  if (sameInGroup.length !== 1 || candidates.length !== 1) return null;
  return data.peaks[candidates[0]];
}

/**
 * Replace each group's initial values with the rows of `_initial.xlsx` (row N = 1, as in Harada's
 * `import_initial_values`). For 2PeaksRatio every row gives one R = A2 / A1 for the coarse search.
 */
export function applyInitialExcel(configs: GroupBatchConfig[], data: InitialExcelData): ApplyInitialResult {
  const applied: string[] = [];
  const skipped: { group_id: string; reason: string }[] = [];
  const warnings: string[] = [];

  const next = configs.map((cfg) => {
    const entries = cfg.peaks.map((pk) => findEntries(pk, cfg.peaks, data));
    const missing = cfg.peaks.filter((_, i) => !entries[i]);
    if (missing.length) {
      skipped.push({ group_id: cfg.group_id, reason: `未検出 ${missing.join(', ')}` });
      return cfg;
    }
    const rows = entries as InitialEntry[][];
    const firstNo = rows[0][0].No;
    const nos = new Set(rows.map((r) => r[0].No));
    if (nos.size > 1) {
      warnings.push(`${cfg.group_id}: No が不一致 (${[...nos].join(' / ')}) → ${firstNo} を使用`);
    }
    const init_peaks: PeakFitParam[] = cfg.peaks.map((pk, i) => {
      const row = rows[i][0];
      const prev = cfg.init_peaks[i];
      return {
        ...(prev ?? { phase: pk.startsWith('fcc') ? 'gamma' : 'alpha_prime', hkl: '', snr: 0 }),
        peak_name: pk,
        No: row.No ?? cfg.init_num,
        y0: row.y0,
        xc: row.xc,
        A: row.A,
        wG: row.wG,
        wL: row.wL,
        FWHM: row.FWHM,
        sigma: row.wG / WG_PER_SIGMA,
        gamma: row.wL / 2,
      } as PeakFitParam;
    });
    const patch: Partial<GroupBatchConfig> = {
      init_peaks,
      init_num: firstNo ?? cfg.init_num,
    };
    if (cfg.peaks.length === 2) {
      const n = Math.min(rows[0].length, rows[1].length);
      const rCand = Array.from({ length: n }, (_, i) => rows[1][i].A / rows[0][i].A).filter(
        (r) => Number.isFinite(r) && r > 0
      );
      if (rCand.length) {
        patch.r_candidates = rCand;
        patch.num_init_val_set = rCand.length;
      }
    }
    applied.push(cfg.group_id);
    return { ...cfg, ...patch };
  });

  return { configs: next, applied, skipped, warnings };
}
