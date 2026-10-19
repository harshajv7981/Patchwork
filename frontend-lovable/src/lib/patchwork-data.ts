export type WorkspaceView = 'overview' | 'discover' | 'ideas' | 'issues' | 'pulls' | 'runs' | 'settings';

export const API_BASE = ((import.meta.env['VITE_API_BASE'] as string | undefined) ?? 'http://localhost:8000').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
 const response = await fetch(`${API_BASE}${path}`, init);
 const data = await response.json().catch(() => ({}));
 if (!response.ok) throw new Error((data as { detail?: string }).detail || `Request failed: ${response.status}`);
 return data as T;
}
export const getJson = <T,>(path: string) => request<T>(path);
export const postJson = <T,>(path: string) => request<T>(path, { method: 'POST' });

// Mirrors backend/app/schemas.py
export type Health = { status: 'ok'; ollama_connected: boolean; configured_model: string; model_available: boolean; provider: string };
export type Repository = { full_name: string; owner: string; name: string; description: string; language: string; stars: number; open_issues: number; fit_score: number; trend_percent: number; url: string };
export type CandidateIssue = { id: number; repository: string; title: string; number: number; label: string; difficulty: string; url: string; suitability_score: number; updated_at: string; ai_analysis?: string | null };
export type Feature = { id: number; repository: string; title: string; description: string; category: string; complexity: string; impact_score: number; implementation_plan: string; suggested_files: string[]; status: string };
export type PullRequest = { id: number; repository: string; title: string; number: number | null; url: string | null; status: string; ai_summary: string | null; created_at: string };
export type Run = { id: number; name: string; status: 'running' | 'completed' | 'failed' | 'needs_review'; summary: string | null; repositories_scanned: number; issues_found: number; created_at: string };
export type Telemetry = { metrics?: Record<string, string>; error?: string };
export type Analysis = { analysis: string; relevant_files: string[]; is_actionable: boolean };

export const pageMeta = (title: string, description: string) => ({ meta: [
 { title: `${title} — Patchwork` }, { name: 'description', content: description },
 { property: 'og:title', content: `${title} — Patchwork` }, { property: 'og:description', content: description },
 { property: 'og:type', content: 'website' }, { name: 'twitter:card', content: 'summary_large_image' },
] });
