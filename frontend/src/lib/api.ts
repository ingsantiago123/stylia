/**
 * Cliente API STYLIA — Comunicación con el backend FastAPI.
 */

// En producción/ngrok el frontend proxea las llamadas al backend via Next.js rewrites.
// En desarrollo local con `npm run dev` puede usarse NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export interface DocumentUploadResponse {
  id: string;
  filename: string;
  original_format: string;
  status: string;
  message: string;
}

export interface ProgressDetail {
  stage: string | null;
  stage_label: string | null;
  stage_current: number | null;
  stage_total: number | null;
  message: string | null;
  eta_seconds: number | null;
  is_stalled: boolean;
  heartbeat_at: string | null;
  stage_started_at: string | null;
}

export interface DocumentListItem {
  id: string;
  filename: string;
  original_format: string;
  status: string;
  total_pages: number | null;
  created_at: string;
  progress: number;
  progress_detail: ProgressDetail | null;
}

export interface DocumentDetail {
  id: string;
  filename: string;
  original_format: string;
  status: string;
  total_pages: number | null;
  config_json: Record<string, unknown>;
  error_message: string | null;
  source_uri: string;
  pdf_uri: string | null;
  docx_uri: string | null;
  created_at: string;
  updated_at: string;
  progress: number;
  progress_detail: ProgressDetail | null;
  pages_summary: Record<string, number>;
  // Token usage & cost (MVP2)
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  llm_cost_usd: number | null;
  // Processing time tracking
  processing_started_at: string | null;
  processing_completed_at: string | null;
  stage_timings: Record<string, number> | null;
  worker_hostname: string | null;
}

export interface PageListItem {
  id: string;
  page_no: number;
  page_type: string;
  render_route: string | null;
  status: string;
  preview_uri: string | null;
  patches_count: number;
  has_corrections: boolean;
}

export interface PatchListItem {
  id: string;
  block_id: string;
  block_no: number | null;
  version: number;
  source: string;
  original_text: string;
  corrected_text: string;
  review_status: string;
  overflow_flag: boolean;
  created_at: string;
  // MVP2 — campos enriquecidos
  category: string | null;
  severity: string | null;
  explanation: string | null;
  confidence: number | null;
  rewrite_ratio: number | null;
  pass_number: number | null;
  model_used: string | null;
  cost_usd: number | null;
  // Lote 4: ruta del complexity router
  route_taken: string | null;
  // Lote 5: quality gates
  gate_results: Array<{
    passed: boolean;
    gate_name: string;
    value: number;
    threshold: number;
    message: string;
    critical: boolean;
  }> | null;
  review_reason: string | null;
  // Auditoría de revisión humana
  reviewed_at: string | null;
  reviewer_note: string | null;
  decision_source: string;
  // Edición manual y recorrección
  edited_text: string | null;
  edited_at: string | null;
  recorrection_count: number;
  // Sprint 3: Audit trail dual-engine
  lt_corrections_json: Array<Record<string, unknown>> | null;
  llm_change_log_json: Array<Record<string, unknown>> | null;
  reverted_lt_changes_json: Array<Record<string, unknown>> | null;
  protected_regions_snapshot: Array<{start: number; end: number; reason: string; text: string}> | null;
}

// Sprint 6: Structural map
export interface ParagraphLocationItem {
  paragraph_index: number;
  location: string;
  page_start: number | null;
  page_end: number | null;
  position_in_page: string | null;
  has_internal_page_break: boolean;
  is_continuation_from_prev_page: boolean;
  paragraph_type: string | null;
}

// Sprint 6: Health check responses
export interface HealthLLM {
  status: string;
  model: string;
  cheap_model: string;
  editorial_model: string;
  latency_ms: number | null;
  error: string | null;
}

export interface HealthLanguageTool {
  status: string;
  url: string;
  latency_ms: number | null;
  version: string | null;
  error: string | null;
}

// =============================================
// MVP2: Perfiles editoriales
// =============================================

export interface PresetInfo {
  key: string;
  name: string;
  description: string;
  icon: string;
  intervention_level: string;
  register: string;
}

export interface StyleProfile {
  id: string;
  doc_id: string;
  preset_name: string | null;
  source: string;
  genre: string | null;
  subgenre: string | null;
  audience_type: string | null;
  audience_age_range: string | null;
  audience_expertise: string;
  register: string;
  tone: string | null;
  intervention_level: string;
  preserve_author_voice: boolean;
  max_rewrite_ratio: number;
  max_expansion_ratio: number;
  target_inflesz_min: number | null;
  target_inflesz_max: number | null;
  style_priorities: string[];
  protected_terms: string[];
  forbidden_changes: string[];
  lt_disabled_rules: string[];
  created_at: string;
  updated_at: string;
}

export interface StyleProfileCreate {
  preset_name?: string | null;
  genre?: string | null;
  subgenre?: string | null;
  audience_type?: string | null;
  audience_age_range?: string | null;
  audience_expertise?: string | null;
  register?: string | null;
  tone?: string | null;
  intervention_level?: string | null;
  preserve_author_voice?: boolean | null;
  max_rewrite_ratio?: number | null;
  max_expansion_ratio?: number | null;
  target_inflesz_min?: number | null;
  target_inflesz_max?: number | null;
  style_priorities?: string[] | null;
  protected_terms?: string[] | null;
  forbidden_changes?: string[] | null;
  lt_disabled_rules?: string[] | null;
}

// =============================================
// Funciones API
// =============================================

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }

  return res.json();
}

export async function listDocuments(): Promise<DocumentListItem[]> {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getDocument(id: string): Promise<DocumentDetail> {
  const res = await fetch(`${API_BASE}/documents/${id}`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function listPages(docId: string): Promise<PageListItem[]> {
  const res = await fetch(`${API_BASE}/documents/${docId}/pages`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getCorrectionFlow(docId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/documents/${docId}/correction-flow`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getDocumentCorrections(id: string): Promise<PatchListItem[]> {
  const res = await fetch(`${API_BASE}/documents/${id}/corrections`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export function downloadPdf(id: string): void {
  window.open(`${API_BASE}/documents/${id}/download/pdf`, "_blank");
}

export function downloadDocx(id: string): void {
  window.open(`${API_BASE}/documents/${id}/download/docx`, "_blank");
}

export function getPagePreviewUrl(docId: string, pageNo: number): string {
  return `${API_BASE}/documents/${docId}/pages/${pageNo}/preview`;
}

export function getCorrectedPagePreviewUrl(docId: string, pageNo: number): string {
  return `${API_BASE}/documents/${docId}/pages/${pageNo}/preview-corrected`;
}

export function getCandidatePagePreviewUrl(docId: string, pageNo: number): string {
  return `${API_BASE}/documents/${docId}/pages/${pageNo}/preview-corrected?mode=candidate`;
}

export interface PageAnnotation {
  patch_ids: string[] | null;
  x_pct: number;
  y_pct: number;
  w_pct: number;
  h_pct: number;
  category: string;
  severity: string | null;
  explanation: string | null;
  confidence: number | null;
  source: string;
  review_status: string;
  original_snippet: string;
  corrected_snippet: string;
}

export async function getPageAnnotations(
  docId: string,
  pageNo: number,
  mode: "candidate" | "final" = "final",
): Promise<PageAnnotation[]> {
  const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNo}/annotations?mode=${mode}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.annotations || [];
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Error ${res.status}`);
}

// =============================================
// MVP2: Perfiles editoriales
// =============================================

export async function listPresets(): Promise<PresetInfo[]> {
  const res = await fetch(`${API_BASE}/presets`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function createProfile(docId: string, data: StyleProfileCreate): Promise<StyleProfile> {
  const res = await fetch(`${API_BASE}/documents/${docId}/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function getProfile(docId: string): Promise<StyleProfile> {
  const res = await fetch(`${API_BASE}/documents/${docId}/profile`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function updateProfile(docId: string, data: StyleProfileCreate): Promise<StyleProfile> {
  const res = await fetch(`${API_BASE}/documents/${docId}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

// =============================================
// Costos (LlmUsage)
// =============================================

export interface CostSummary {
  total_cost_usd: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_documents: number;
  total_calls: number;
  avg_cost_per_document: number;
  avg_cost_per_call: number;
  model_breakdown: Array<{
    model: string;
    calls: number;
    tokens: number;
    cost: number;
  }>;
  pricing: {
    model: string;
    input_per_1m: number;
    output_per_1m: number;
  };
}

export interface DocumentCostItem {
  doc_id: string;
  filename: string;
  status: string;
  total_pages: number | null;
  total_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  created_at: string;
}

export interface ParagraphCostItem {
  id: string;
  paragraph_index: number;
  location: string;
  call_type: string;
  model_used: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  created_at: string;
}

export async function getCostSummary(): Promise<CostSummary> {
  const res = await fetch(`${API_BASE}/costs/summary`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getCostDocuments(skip = 0, limit = 50): Promise<DocumentCostItem[]> {
  const res = await fetch(`${API_BASE}/costs/documents?skip=${skip}&limit=${limit}`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getDocumentCosts(docId: string): Promise<ParagraphCostItem[]> {
  const res = await fetch(`${API_BASE}/documents/${docId}/costs`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function processDocument(docId: string): Promise<{ message: string; task_id: string }> {
  const res = await fetch(`${API_BASE}/documents/${docId}/process`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

// =============================================
// Revisión humana (Human-in-the-Loop)
// =============================================

export interface ReviewSummary {
  total_patches: number;
  auto_accepted: number;
  pending: number;
  accepted: number;
  rejected: number;
  manual_review: number;
  gate_rejected: number;
  bulk_finalized: number;
  can_finalize_strict: boolean;
  can_finalize_quick: boolean;
  render_version: number;
  by_severity: Record<string, number>;
  by_page: Record<number, Record<string, number>>;
}

export async function getReviewSummary(docId: string): Promise<ReviewSummary> {
  const res = await fetch(`${API_BASE}/documents/${docId}/review-summary`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function reviewCorrection(
  docId: string,
  patchId: string,
  action: "accepted" | "rejected",
  reviewerNote?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}/corrections/${patchId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reviewer_note: reviewerNote || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
}

export async function bulkReviewCorrections(
  docId: string,
  patchIds: string[],
  action: "accepted" | "rejected",
  reviewerNote?: string
): Promise<{ count: number }> {
  const res = await fetch(`${API_BASE}/documents/${docId}/corrections/bulk-action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      patch_ids: patchIds,
      action,
      reviewer_note: reviewerNote || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function finalizeDocument(
  docId: string,
  mode: "quick" | "strict" = "quick",
  applyMode: "accepted_only" | "accepted_and_auto" = "accepted_and_auto"
): Promise<{ message: string; task_id: string; finalize_mode: string }> {
  const res = await fetch(`${API_BASE}/documents/${docId}/finalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, apply_mode: applyMode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function reopenDocument(
  docId: string
): Promise<{ message: string; status: string; render_version: number }> {
  const res = await fetch(`${API_BASE}/documents/${docId}/reopen`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function getSingleCorrection(
  docId: string,
  patchId: string
): Promise<PatchListItem> {
  const res = await fetch(`${API_BASE}/documents/${docId}/corrections/${patchId}`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function manualEditCorrection(
  docId: string,
  patchId: string,
  editedText: string,
  reviewerNote?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${docId}/corrections/${patchId}/edit`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      edited_text: editedText,
      reviewer_note: reviewerNote || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
}

export async function rerenderCandidatePreview(
  docId: string
): Promise<{ task_id: string; message: string }> {
  const res = await fetch(`${API_BASE}/documents/${docId}/rerender-preview`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function getTaskStatus(
  taskId: string
): Promise<{ task_id: string; status: string; ready: boolean }> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/status`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function recorrectPatch(
  docId: string,
  patchId: string,
  feedback: string
): Promise<{ message: string; task_id: string; recorrection_count: number }> {
  const res = await fetch(`${API_BASE}/documents/${docId}/corrections/${patchId}/recorrect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

// =============================================
// Análisis editorial (MVP2 Lote 3)
// =============================================

export interface SectionSummaryItem {
  section_index: number;
  section_title: string | null;
  start_paragraph: number;
  end_paragraph: number;
  summary_text: string | null;
  topic: string | null;
  local_tone: string | null;
  active_terms: string[];
  transition_from_previous: string | null;
}

export interface TermRegistryItem {
  term: string;
  normalized_form: string;
  frequency: number;
  first_occurrence_paragraph: number;
  is_protected: boolean;
  decision: string;
}

export interface InferredProfile {
  genre: string | null;
  audience_type: string | null;
  register: string | null;
  tone: string | null;
  spanish_variant: string | null;
  key_terms: string[];
  suggested_intervention: string | null;
}

export interface AnalysisResult {
  doc_id: string;
  status: string;
  inferred_profile: InferredProfile | null;
  sections: SectionSummaryItem[];
  terms: TermRegistryItem[];
  paragraph_classifications: Array<{
    paragraph_index: number;
    location: string;
    paragraph_type: string;
    requires_llm: boolean;
    text_preview: string;
  }>;
  stats: Record<string, unknown>;
}

export async function getDocumentAnalysis(docId: string): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/documents/${docId}/analysis`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

// =============================================
// Corrección paralela por lotes
// =============================================

export interface CorrectionBatchStatus {
  batch_index: number;
  start_paragraph: number;
  end_paragraph: number;
  paragraphs_total: number;
  paragraphs_corrected: number;
  patches_count: number;
  status: string; // pending|running|completed|failed
  lt_pass_completed: boolean;
  llm_pass_completed: boolean;
  boundary_checked: boolean;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export async function getCorrectionBatches(docId: string): Promise<CorrectionBatchStatus[]> {
  const res = await fetch(`${API_BASE}/documents/${docId}/correction-batches`);
  if (!res.ok) return [];
  return res.json();
}

// Sprint 6: Structural map & health checks
export async function getStructuralMap(docId: string): Promise<ParagraphLocationItem[]> {
  const res = await fetch(`${API_BASE}/documents/${docId}/structural-map`);
  if (!res.ok) return [];
  return res.json();
}

export async function getCrossPageParagraphs(docId: string): Promise<ParagraphLocationItem[]> {
  const res = await fetch(`${API_BASE}/documents/${docId}/cross-page-paragraphs`);
  if (!res.ok) return [];
  return res.json();
}

export async function checkLLMHealth(): Promise<HealthLLM> {
  const res = await fetch(`${API_BASE}/health/llm`);
  if (!res.ok) throw new Error(`LLM health check failed: ${res.status}`);
  return res.json();
}

export async function checkLanguageToolHealth(): Promise<HealthLanguageTool> {
  const res = await fetch(`${API_BASE}/health/languagetool`);
  if (!res.ok) throw new Error(`LanguageTool health check failed: ${res.status}`);
  return res.json();
}

// =============================================
// Plan v4: Auditoría LLM
// =============================================

export interface LlmAuditStats {
  total_calls: number;
  pass1_calls: number;
  pass2_calls: number;
  paragraphs_with_audit: number;
  total_reversions_detected: number;
  errors: number;
}

export interface LlmAuditEntry {
  id: string;
  paragraph_index: number | null;
  location: string | null;
  pass_number: number;
  call_purpose: string;
  model_used: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number | null;
  has_error: boolean;
  error_text: string | null;
  created_at: string | null;
  // Detail (only available in /llm-audit/{idx})
  request_payload?: Record<string, unknown>;
  response_payload?: Record<string, unknown>;
}

export interface LlmAuditDiff {
  doc_id: string;
  paragraph_index: number;
  original_text: string | null;
  corrected_pass1_text: string | null;
  corrected_final_text: string | null;
  has_pass2: boolean;
  pass2_audit: {
    reverted_destructions: Array<{ original_term: string; pass1_changed_to: string; reason: string; severity: string }>;
    style_improvements: Array<{ original_fragment: string; improved_fragment: string; category: string; explanation: string }>;
    confidence: number | null;
    pass1_quality: string | null;
  } | null;
  pass1: { request_payload: Record<string, unknown> | null; response_payload: Record<string, unknown> | null; tokens: number | null; latency_ms: number | null; model_used: string | null } | null;
  pass2: { request_payload: Record<string, unknown> | null; response_payload: Record<string, unknown> | null; tokens: number | null; latency_ms: number | null; model_used: string | null } | null;
}

export interface GlobalDocumentContext {
  doc_id: string;
  global_summary: string | null;
  dominant_voice: string | null;
  dominant_register: string | null;
  key_themes: Array<{ theme: string; weight: number }>;
  protected_globals: Array<{ term: string; reason: string }>;
  style_fingerprint: Record<string, unknown>;
  total_paragraphs: number | null;
  created_at: string | null;
}

export async function getLlmAudit(
  docId: string,
  filters?: { pass_number?: number; has_error?: boolean }
): Promise<{ stats: LlmAuditStats; entries: LlmAuditEntry[] }> {
  const params = new URLSearchParams();
  if (filters?.pass_number != null) params.set("pass_number", String(filters.pass_number));
  if (filters?.has_error != null) params.set("has_error", String(filters.has_error));
  params.set("limit", "500");
  const res = await fetch(`${API_BASE}/documents/${docId}/llm-audit?${params}`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getLlmAuditParagraph(
  docId: string,
  paragraphIndex: number
): Promise<{ doc_id: string; paragraph_index: number; calls: LlmAuditEntry[] }> {
  const res = await fetch(`${API_BASE}/documents/${docId}/llm-audit/${paragraphIndex}`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getLlmAuditDiff(
  docId: string,
  paragraphIndex: number
): Promise<LlmAuditDiff> {
  const res = await fetch(`${API_BASE}/documents/${docId}/llm-audit/diff/${paragraphIndex}`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function getGlobalContext(docId: string): Promise<GlobalDocumentContext> {
  const res = await fetch(`${API_BASE}/documents/${docId}/global-context`);
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}
