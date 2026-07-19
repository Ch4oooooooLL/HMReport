export interface Source {
  id: string
  source_type: string
  absolute_path: string
  filename: string
  availability: string
  fingerprint: string
}

export interface RunTask {
  id: string
  task_type: string
  status: string
  progress_current: number
  progress_total: number
  progress_message: string
}

export interface Run {
  id: string
  project_id: string
  run_no: number
  name: string
  status: string
  progress: number
  tasks: RunTask[]
  input_snapshot: Record<string, { path: string; fingerprint: string }>
}

export interface Project {
  id: string
  name: string
  code: string
  solver: string
  unit_system: string
  analysis_type: string
  description: string
  status: string
  workspace_path: string
  latest_run_id?: string
  sources?: Source[]
  runs?: Run[]
}

export interface CaptureVersion {
  id: string
  version_no: number
  image_path: string
  view_state: Record<string, unknown>
  is_current: number
}

export interface Capture {
  id: string
  name: string
  view_name: string
  review_status: string
  current_version_id: string
  versions: CaptureVersion[]
}

export interface Hotspot {
  id: string
  result_kind: string
  subcase: string
  rank: number
  entity_type: string
  entity_id: number
  component_name: string
  value: number
  unit: string
  coordinate: number[]
  classification: string
  review_status: string
  captures?: Capture[]
}

export interface ReportElement {
  type: string
  text?: string
  src?: string
  x: number
  y: number
  w: number
  h: number
}

export interface ReportSlide {
  id: string
  title: string
  layout: string
  elements: ReportElement[]
  notes: string
}

export interface ReportDocument {
  id: string
  run_id: string
  template_id: string
  page_size: string
  theme: Record<string, unknown>
  sections: unknown[]
  slides: ReportSlide[]
}

