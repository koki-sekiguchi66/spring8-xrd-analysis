import type { FitLimitConfig, GroupBatchConfig } from '../types/xrd';

type Engine = GroupBatchConfig['engine'];

/**
 * Defaults of Harada's original scripts (mirrors the backend fitters):
 * 1Peak = fittning_1peaks_ver7.0_NH.py, MultiPeaks = fitting_multi peaks_csv_ver4.0.0.py,
 * 2PeaksRatio = fitting_2peaks_csv_fixed_ratio_diff_inits_ver10.py,
 * 3PeaksLuders = fitting_3peaks_afterLuders_csv_ver4.py.
 */
export const ENGINE_RUN_DEFAULTS: Record<Engine, { residual_limit: number; max_attempts: number }> = {
  '1Peak': { residual_limit: 0.7, max_attempts: 5 },
  MultiPeaks: { residual_limit: 60, max_attempts: 10 },
  '2PeaksRatio': { residual_limit: 200, max_attempts: 10 },
  '3PeaksLuders': { residual_limit: 350, max_attempts: 5 },
};

const ONE_PEAK: FitLimitConfig = {
  center_min_offset: -0.05,
  center_max_offset: 0.2,
  amplitude_min_factor: 0.7,
  amplitude_max_factor: 1.4,
  amplitude_min_offset: 0,
  amplitude_max_offset: 10,
  sigma_min_factor: 0.8,
  sigma_max_factor: 1.3,
  sigma_min_offset: -0.001,
  sigma_max_offset: 0.001,
  gamma_min_factor: 0.8,
  gamma_max_factor: 1.3,
  gamma_min_offset: -0.001,
  gamma_max_offset: 0.001,
};

const MULTI: FitLimitConfig = {
  center_min_offset: -0.02,
  center_max_offset: 0.05,
  amplitude_min_factor: 0.9,
  amplitude_max_factor: 1.1,
  amplitude_min_offset: 0,
  amplitude_max_offset: 10,
  sigma_min_factor: 0.9,
  sigma_max_factor: 1.1,
  sigma_min_offset: -0.0001,
  sigma_max_offset: 0.0001,
  gamma_min_factor: 0.9,
  gamma_max_factor: 1.1,
  gamma_min_offset: -0.0001,
  gamma_max_offset: 0.0001,
};

const RATIO2: FitLimitConfig[] = [
  {
    center_min_offset: -0.015,
    center_max_offset: 0.005,
    amplitude_min_factor: 0.95,
    amplitude_max_factor: 1.05,
    amplitude_min_offset: 0,
    amplitude_max_offset: 10,
    sigma_min_factor: 0.99,
    sigma_max_factor: 1.02,
    sigma_min_offset: 0,
    sigma_max_offset: 1e-10,
    gamma_min_factor: 0.99,
    gamma_max_factor: 1.005,
    gamma_min_offset: 0,
    gamma_max_offset: 1e-10,
  },
  {
    center_min_offset: -0.01,
    center_max_offset: 0.005,
    amplitude_min_factor: 0.95,
    amplitude_max_factor: 1.05,
    amplitude_min_offset: 0,
    amplitude_max_offset: 10,
    sigma_min_factor: 0.99,
    sigma_max_factor: 1.02,
    sigma_min_offset: 0,
    sigma_max_offset: 1e-10,
    gamma_min_factor: 0.99,
    gamma_max_factor: 1.005,
    gamma_min_offset: 0,
    gamma_max_offset: 1e-10,
  },
];

const LUDERS: FitLimitConfig[] = [
  {
    center_min_offset: -0.01,
    center_max_offset: 0.002,
    amplitude_min_factor: 0.95,
    amplitude_max_factor: 1.05,
    amplitude_min_offset: 0,
    amplitude_max_offset: 10,
    sigma_min_factor: 0.99,
    sigma_max_factor: 1.1,
    sigma_min_offset: 0,
    sigma_max_offset: 1e-15,
    gamma_min_factor: 0.99,
    gamma_max_factor: 1.01,
    gamma_min_offset: 0,
    gamma_max_offset: 1e-15,
  },
  {
    center_min_offset: -0.01,
    center_max_offset: 0.01,
    amplitude_min_factor: 0.9,
    amplitude_max_factor: 1.1,
    amplitude_min_offset: 0,
    amplitude_max_offset: 10,
    sigma_min_factor: 0.99,
    sigma_max_factor: 1.01,
    sigma_min_offset: 0,
    sigma_max_offset: 1e-15,
    gamma_min_factor: 0.99,
    gamma_max_factor: 1.001,
    gamma_min_offset: 0,
    gamma_max_offset: 1e-10,
  },
  {
    center_min_offset: -0.03,
    center_max_offset: 0.08,
    amplitude_min_factor: 0.9,
    amplitude_max_factor: 1.1,
    amplitude_min_offset: 20,
    amplitude_max_offset: 10,
    sigma_min_factor: 0.9,
    sigma_max_factor: 1.005,
    sigma_min_offset: 0,
    sigma_max_offset: 1e-15,
    gamma_min_factor: 0.9,
    gamma_max_factor: 1.005,
    gamma_min_offset: 0,
    gamma_max_offset: 1e-10,
  },
];

/** Per-frame limit defaults of the given engine for peak index `pkIdx` (0-based). */
export function defaultLimitsFor(engine: Engine, pkIdx: number): FitLimitConfig {
  switch (engine) {
    case '1Peak':
      return { ...ONE_PEAK };
    case '2PeaksRatio':
      return { ...RATIO2[Math.min(pkIdx, RATIO2.length - 1)] };
    case '3PeaksLuders':
      return { ...LUDERS[Math.min(pkIdx, LUDERS.length - 1)] };
    default:
      return { ...MULTI };
  }
}
