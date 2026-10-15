export type ComponentMesh = { id: string; role: string; fingerprint: string; positions: number[]; indices: number[]; bounds: { min_mm: number[]; max_mm: number[]; size_mm: number[] }; volume_mm3: number };
export type SceneData = { units: string; components: ComponentMesh[] };
export type RequirementRow = { id: string; description: string; status: string; reason: string; mandatory: boolean; result?: { actual: unknown; expected: unknown; unit: string | null } };
export type RunReport = { outcome: string; ready_for_review: boolean; coverage: RequirementRow[]; errors: string[]; blocking_reasons: string[]; elapsed_seconds: number; assumptions: {description: string}[] };
export type Revision = { id: string; status: string; scene: boolean; summary: string; elapsed_seconds?: number; checks?: number; requirements?: number };
export type Design = { id: string; title: string; status: string; questions: string[]; messages: { role: string; text: string; time: string; questions?: string[]; revision?: string; kind?: string }[]; revisions: Revision[]; latest_revision: string | null; display_revision: string | null; updated: string };
export type RevisionData = { revision: string; scene: SceneData | null; report: RunReport | null; files: string[]; comparison?: { baseline: string; components: {added: string[]; removed: string[]; changed: Record<string, unknown>}; requirements: {added: string[]; removed: string[]; modified: Record<string, unknown>} } | null };
export type Job = { id: string; status: string; design_id: string; error?: string };
