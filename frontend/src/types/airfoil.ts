export interface AirfoilFeatures {
  max_thickness:    number;
  max_thickness_x:  number;
  max_camber:       number;
  max_camber_x:     number;
  is_symmetric:     boolean;
}

export interface AirfoilResult {
  name:     string;
  x:        number[];
  y:        number[];
  features: AirfoilFeatures;
  source?:  string;
}

export interface PolarResult {
  alpha:     number[];
  cl:        number[];
  cd:        number[];
  ld:        number[];
  converged: boolean;
  source:    "xfoil" | "approximation";
}

export interface PolarMetrics {
  best_ld:         number;
  best_ld_alpha:   number;
  max_cl:          number;
  stall_alpha:     number;
  cl_at_target:    number;
  cd_at_target:    number;
  ld_at_target:    number;
  drag_bucket_width?: number;
}

export interface ManualParams {
  max_camber:    number;
  camber_pos:    number;
  max_thickness: number;
  reynolds:      number;
}

export interface DBResult {
  index:         number;
  name:          string;
  file:          string;
  max_thickness: number;
  max_camber:    number;
  is_symmetric:  boolean;
}

export interface CompareResult {
  a: { name: string; polar: PolarResult; metrics: PolarMetrics };
  b: { name: string; polar: PolarResult; metrics: PolarMetrics };
}

export interface OptimizeRequest {
  n_candidates: number;
  target:       "best_ld" | "max_cl" | "min_cd";
  reynolds:     number;
}

export interface OptimizationCandidate {
  name:     string;
  x:        number[];
  y:        number[];
  features: AirfoilFeatures;
  polar:    PolarResult;
  metrics:  PolarMetrics;
  latent:   number[] | null;
}

export interface VaeStatus {
  available: boolean;
  stats: { mean: number[]; std: number[] } | null;
}
