export interface PreprocessPreviewData {
  num: number;
  filename: string;
  th_min: number;
  method_used: string;
  x: number[];
  y_raw: number[];
  y_despiked: number[];
  anchors_x: number[];
  anchors_y: number[];
  monotonic_x: number[];
  monotonic_y: number[];
  y_background: number[];
  y_corrected: number[];
}

export interface PreprocessRunResponse {
  status: string;
  folder_path: string;
  specimen_name: string;
  separation: {
    already_separated: boolean;
    moved_tth_count: number;
    moved_others_count: number;
    total_tth_count: number;
  };
  background_removal: {
    folder_path: string;
    bcg_dir: string;
    processed_count: number;
    skipped_cached: boolean;
    nums: number[];
    th_min: number;
  };
  nums: number[];
  preview: PreprocessPreviewData;
}

export interface PhaseMarker {
  name: string;
  phase: 'gamma' | 'alpha_prime';
  phase_label: string;
  hkl: string;
  theoretical_2th: number;
  observed_2th: number;
  intensity: number;
}

export interface PeakFitParam {
  peak_name: string;
  phase: string;
  hkl: string;
  No: number;
  y0: number;
  xc: number;
  A: number;
  wG: number;
  wL: number;
  FWHM: number;
  sigma: number;
  gamma: number;
  snr: number;
}

export interface CandidateFitResult {
  group_id: string;
  num: number;
  filename: string;
  range_min: number;
  range_max: number;
  vary_y0: boolean;
  r_squared: number;
  rmse: number;
  relative_residual: number;
  is_weak: boolean;
  peaks: PeakFitParam[];
  x: number[];
  y_obs: number[];
  y_fit: number[];
  residual: number[];
  components: Record<string, number[]>;
  error?: string;
}

export interface CandidateGroup {
  group_id: string;
  label: string;
  category: 'single' | 'multi_pair';
  peaks: string[];
  phases: string[];
  range_min: number;
  range_max: number;
  recommended_stage: 'early' | 'late';
  default_engine: '1Peak' | '2PeaksRatio' | '3PeaksLuders' | 'MultiPeaks';
  supported_engines: ('1Peak' | '2PeaksRatio' | '3PeaksLuders' | 'MultiPeaks')[];
  default_selected: boolean;
  description: string;
  recommended_num: number;
  selected_num: number;
  selected: boolean;
  is_weak: boolean;
  is_custom?: boolean;
  fits_by_num: Record<string, CandidateFitResult>;
}

export interface FullProfileData {
  num: number;
  filename: string;
  x: number[];
  y: number[];
  markers: PhaseMarker[];
}

export interface InitialAutoDetectResponse {
  folder_path: string;
  mode: string;
  available_nums: number[];
  selected_nums: number[];
  early_num: number;
  late_num: number;
  dimt_onset_estimate: number;
  profiles_by_num: Record<string, FullProfileData>;
  candidate_groups: CandidateGroup[];
}

export interface FitLimitConfig {
  center_min_offset: number;
  center_max_offset: number;
  amplitude_min_factor: number;
  amplitude_max_factor: number;
  amplitude_min_offset: number;
  amplitude_max_offset: number;
  sigma_min_factor: number;
  sigma_max_factor: number;
  sigma_min_offset: number;
  sigma_max_offset: number;
  gamma_min_factor: number;
  gamma_max_factor: number;
  gamma_min_offset: number;
  gamma_max_offset: number;
}

export interface GroupBatchConfig {
  group_id: string;
  engine: '1Peak' | '2PeaksRatio' | '3PeaksLuders' | 'MultiPeaks';
  peaks: string[];
  init_num: number;
  init_peaks: PeakFitParam[];
  th_min?: number;
  th_max?: number;
  fitting_range_min: number;
  fitting_range_max: number;
  dimt_onset_num: number;
  undeform_initial: number;
  undeform_end: number;
  R: number;
  R2: number;
  residual_limit: number;
  max_attempts: number;
  newly_forms_peak?: number[];
  use_bcc211_constraint?: boolean;
  bcc110_center_tol_deg?: number;
  /** Constant background y0 in the window (Origin y0 + Voigt). Off = Harada's scripts. */
  fit_y0?: boolean;
  /** 3PeaksLuders: R = best_R of this 2PeaksRatio group (cold-rolled flow) */
  R_source_group?: string;
  /** Step 2 fits of this group per representative frame (num -> peaks), for re-choosing the initial frame */
  init_options?: Record<string, PeakFitParam[]>;
  /** Frame chosen in Step 2 (initial frame for 1Peak / MultiPeaks) */
  step2_num?: number;
  default_fit_limits?: Record<string, FitLimitConfig>;
  min_peak_separation?: number;
  suppress_before_onset?: boolean;
  initial_ep_region?: number;
  end_ep_region?: number;
  num_init_val_set?: number;
  vib_ratio_fine?: number;
  r_candidates?: number[];
  final_num?: number;
  v3_center_cap?: number;
}

export interface BatchGroupResult {
  group_id: string;
  sheet_name: string;
  engine: string;
  peaks: string[];
  th_min: number;
  th_max: number;
  rows: Record<string, number>[];
  outlier_nums: number[];
  best_R?: number;
  history_R?: number[];
  history_residual?: number[];
}

export interface VideoMetadataItem {
  video_path: string;
  filename: string;
  stem: string;
  extension: string;
  fps: number;
  frame_count: number;
  duration_sec: number;
  width: number;
  height: number;
}

export interface VideoInspectResponse {
  mode: 'single' | 'folder';
  target_path: string;
  video_count: number;
  videos: VideoMetadataItem[];
  total_duration_sec: number;
  recommended_stop_sec: number;
  expected_total_frames: number;
  default_output_dir: string;
  default_basename: string;
}

export interface BatchRefitRepairedItem {
  group_id: string;
  num: number;
  updated_row: Record<string, number>;
  rmse: number;
  relative_residual: number;
  r_squared: number | null;
  is_outlier?: boolean;
}

export interface BatchRefitResponse {
  status: string;
  repaired_count: number;
  repaired_items: BatchRefitRepairedItem[];
  saved_path?: string;
}

export interface WilliamsonHallPoint {
  peak: string;
  K_C: number;
  dK: number;
}

export interface PhysicsAnalysisResponse {
  status: string;
  source: string;
  wavelength_nm: number;
  wavelength_source?: 'user' | 'default';
  zero_alpha_before_num?: number;
  analysis_min_num?: number | null;
  analysis_max_num?: number | null;
  /** First frame of a sustained collapse of the total fitted intensity (fracture), if any */
  fracture_num_estimate?: number | null;
  energy_kev: number;
  gamma_peaks: string[];
  alpha_prime_peaks: string[];
  available_reflections?: string[];
  excluded_reflections?: string[];
  R_values?: Record<string, number>;
  b_iso_A2?: number;
  r_lattice?: 'measured' | 'reference';
  a_gamma_for_R_nm?: number;
  a_alpha_prime_for_R_nm?: number;
  a_gamma_median_nm?: number;
  a_alpha_prime_median_nm?: number;
  nums: number[];
  f_gamma: (number | null)[];
  f_alpha_prime: (number | null)[];
  kinetics_fit?: {
    model?: string;
    fs: number;
    beta: number;
    onset_num: number;
    n: number;
    fitted_curve: number[];
  } | null;
  rho_gamma_m2: (number | null)[];
  rho_alpha_prime_m2: (number | null)[];
  microstrain_gamma_pct: (number | null)[];
  microstrain_alpha_prime_pct: (number | null)[];
  a_gamma_nm: (number | null)[];
  a_alpha_prime_nm: (number | null)[];
  lattice_strains_ue: Record<string, (number | null)[]>;
  dislocation_by_peak_m2: Record<string, (number | null)[]>;
  williamson_hall_snapshots: Record<
    string,
    {
      num: number;
      gamma: WilliamsonHallPoint[];
      alpha_prime: WilliamsonHallPoint[];
    }
  >;
  summary_rows: Record<string, number | null>[];
}
