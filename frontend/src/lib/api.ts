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

export interface DocumentListItem {
  id: string;
  filename: string;
  original_format: string;
  status: string;
  total_pages: number | null;
  created_at: string;
  progress: number;
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
  pages_summary: Record<string, number>;
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

export interface PageAnnotation {
  x_pct: number;
  y_pct: number;
  w_pct: number;
  h_pct: number;
  category: string;
  severity: string | null;
  explanation: string | null;
  confidence: number | null;
  source: string;
  original_snippet: string;
  corrected_snippet: string;
}

export async function getPageAnnotations(docId: string, pageNo: number): Promise<PageAnnotation[]> {
  const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNo}/annotations`);
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
