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

export interface InitialBlockRow {
  No: number | null;
  entries: Record<string, Omit<InitialEntry, 'No'>>;
}

/** One block of the workbook: peak names of the header row and its initial-value rows. */
export interface InitialBlock {
  peaks: string[];
  rows: InitialBlockRow[];
}

export interface InitialExcelData {
  excel_path: string;
  peaks: Record<string, InitialEntry[]>;
  blocks?: InitialBlock[];
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

/** Block peak name for each group peak (exact name, or an alias unique on both sides), or null. */
function mapBlockPeaks(block: InitialBlock, cfgPeaks: string[]): string[] | null {
  const out: string[] = [];
  for (const pk of cfgPeaks) {
    if (block.peaks.includes(pk)) {
      out.push(pk);
      continue;
    }
    const key = canonicalPeakKey(pk);
    const inGroup = cfgPeaks.filter((p) => canonicalPeakKey(p) === key);
    const inBlock = block.peaks.filter((n) => canonicalPeakKey(n) === key);
    if (!key || inGroup.length !== 1 || inBlock.length !== 1) return null;
    out.push(inBlock[0]);
  }
  return out;
}

/**
 * Block for a group, chosen like Harada's procedure: 2PeaksRatio = the latest frame at or before the
 * DIMT onset, 3PeaksLuders = the latest frame at or after it, otherwise the Step 2 frame (`init_num`)
 * or the first block. Blocks holding exactly the group's peaks are preferred.
 */
function chooseBlock(
  cfg: GroupBatchConfig,
  blocks: InitialBlock[]
): { block: InitialBlock; names: string[] } | { reason: string } {
  const matches = blocks
    .map((block) => ({ block, names: mapBlockPeaks(block, cfg.peaks) }))
    .filter((m): m is { block: InitialBlock; names: string[] } => m.names !== null && m.block.rows.length > 0)
    .sort((a, b) => Number(b.block.peaks.length === cfg.peaks.length) - Number(a.block.peaks.length === cfg.peaks.length));
  if (!matches.length) return { reason: `ブロックなし (${cfg.peaks.join(', ')})` };
  const no = (m: { block: InitialBlock }) => m.block.rows[0].No ?? cfg.init_num;
  const onset = cfg.dimt_onset_num;
  const latest = (list: typeof matches) =>
    list.reduce((best, m) => (no(m) > no(best) ? m : best), list[0]);
  if (cfg.engine === '2PeaksRatio') {
    const c = matches.filter((m) => no(m) <= onset);
    return c.length ? latest(c) : { reason: `変態前 (No ≤ ${onset}) のブロックなし` };
  }
  if (cfg.engine === '3PeaksLuders') {
    const c = matches.filter((m) => no(m) >= onset);
    return c.length ? latest(c) : { reason: `変態後 (No ≥ ${onset}) のブロックなし` };
  }
  const target = cfg.step2_num ?? cfg.init_num;
  return matches.find((m) => no(m) === target) ?? matches[0];
}

function applyBlocks(configs: GroupBatchConfig[], blocks: InitialBlock[]): ApplyInitialResult {
  const applied: string[] = [];
  const skipped: { group_id: string; reason: string }[] = [];
  const next = configs.map((cfg) => {
    const pick = chooseBlock(cfg, blocks);
    if ('reason' in pick) {
      skipped.push({ group_id: cfg.group_id, reason: pick.reason });
      return cfg;
    }
    const { block, names } = pick;
    const row0 = block.rows[0];
    const No = row0.No ?? cfg.init_num;
    const init_peaks: PeakFitParam[] = cfg.peaks.map((pk, i) => {
      const e = row0.entries[names[i]];
      const prev = cfg.init_peaks[i];
      return {
        ...(prev ?? { phase: pk.startsWith('fcc') ? 'gamma' : 'alpha_prime', hkl: '', snr: 0 }),
        peak_name: pk,
        No,
        y0: e.y0,
        xc: e.xc,
        A: e.A,
        wG: e.wG,
        wL: e.wL,
        FWHM: e.FWHM,
        sigma: e.wG / WG_PER_SIGMA,
        gamma: e.wL / 2,
      } as PeakFitParam;
    });
    const patch: Partial<GroupBatchConfig> = { init_peaks, init_num: No };
    if (cfg.peaks.length === 2) {
      // ver10: every row of the block is one initial-value set -> R = A2 / A1
      const rCand = block.rows
        .filter((r) => r.entries[names[0]] && r.entries[names[1]])
        .map((r) => r.entries[names[1]].A / r.entries[names[0]].A)
        .filter((r) => Number.isFinite(r) && r > 0);
      if (rCand.length) {
        patch.r_candidates = rCand;
        patch.num_init_val_set = rCand.length;
        if (cfg.engine === '2PeaksRatio') patch.R = Number(rCand[0].toFixed(6));
      }
    }
    applied.push(cfg.group_id);
    return { ...cfg, ...patch };
  });
  return { configs: next, applied, skipped, warnings: [] };
}

/**
 * Replace each group's initial values with `_initial.xlsx` (row N = 1, as in Harada's
 * `import_initial_values`). For 2PeaksRatio every row gives one R = A2 / A1 for the coarse search.
 */
export function applyInitialExcel(configs: GroupBatchConfig[], data: InitialExcelData): ApplyInitialResult {
  if (data.blocks && data.blocks.length) return applyBlocks(configs, data.blocks);
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
