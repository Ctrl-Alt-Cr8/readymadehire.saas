const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8080";

export interface UserConfig {
  name: string;
  target_roles: string[];
  location_pref: string;
  keywords: string[];
  summary: string;
  constraints: string;
  recipient_email: string;
}

export interface ParsedProfile {
  name: string;
  target_roles: string[];
  location_pref: string;
  summary: string;
  constraints: string;
  keywords: string[];
}

export interface OnboardingData {
  name: string;
  target_roles: string[];
  location_pref: string;
  keywords: string[];
  summary: string;
  constraints: string;
  recipient_email: string;
  interview_answers?: string;
  min_salary_k?: number;
  years_experience?: number;
  job_type?: string;
}

export interface Job {
  id: number;
  title: string;
  company: string;
  decision: "APPLY" | "REVIEW" | "SKIP";
  score: number;
  url?: string;
}

export interface RunWithJobs {
  id: number;
  run_at: string;
  jobs_fetched: number;
  jobs_apply: number;
  jobs_review: number;
  jobs_skip: number;
  estimated_cost: number;
  jobs: Job[];
}

export async function getRuns(token: string): Promise<RunWithJobs[]> {
  const res = await fetch(`${AGENT_URL}/runs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Agent error: ${res.status}`);
  return res.json();
}

export async function getConfig(token: string): Promise<UserConfig | null> {
  const res = await fetch(`${AGENT_URL}/config`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Agent error: ${res.status}`);
  return res.json();
}

export async function parseResume(token: string, file: File, interviewAnswers = ""): Promise<ParsedProfile> {
  const form = new FormData();
  form.append("file", file);
  if (interviewAnswers) form.append("interview_answers", interviewAnswers);
  const res = await fetch(`${AGENT_URL}/parse-resume`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Agent error: ${res.status}`);
  }
  return res.json();
}

export async function submitOnboarding(token: string, data: OnboardingData): Promise<void> {
  const res = await fetch(`${AGENT_URL}/onboard`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Agent error: ${res.status}`);
  }
}

export async function triggerRun(token: string): Promise<void> {
  const res = await fetch(`${AGENT_URL}/run-agent`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Agent error: ${res.status}`);
  }
}
