/**
 * Cliente API STYLIA — Comunicación con el backend FastAPI.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Error ${res.status}`);
}
