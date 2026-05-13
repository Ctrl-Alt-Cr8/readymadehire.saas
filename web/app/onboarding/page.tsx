"use client";

import { useEffect, useRef, useState, KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { parseResume, submitOnboarding } from "@/lib/agent";
import type { ParsedProfile } from "@/lib/agent";

type Step = "choose" | "interview" | "form";
type WorkEnv = "Remote" | "Hybrid" | "In-person" | "";
type JobType = "Full-time" | "Contract" | "Part-time" | "Any" | "";

interface Interview {
  roles_wanted: string;
  industries: string;
  work_env: WorkEnv;
  job_type: JobType;
  min_salary_k: string;
  years_experience: string;
  other: string;
}

interface FormState {
  name: string;
  target_roles: string;
  location_pref: string;
  summary: string;
  constraints: string;
  keywords: string[];
  recipient_email: string;
}

const BLANK_INTERVIEW: Interview = {
  roles_wanted: "",
  industries: "",
  work_env: "",
  job_type: "",
  min_salary_k: "",
  years_experience: "",
  other: "",
};

const BLANK_FORM: FormState = {
  name: "",
  target_roles: "",
  location_pref: "",
  summary: "",
  constraints: "",
  keywords: [],
  recipient_email: "",
};

function interviewToText(iv: Interview): string {
  const parts: string[] = [];
  if (iv.roles_wanted) parts.push(`Looking for: ${iv.roles_wanted}`);
  if (iv.industries) parts.push(`Industries: ${iv.industries}`);
  if (iv.work_env) parts.push(`Work environment: ${iv.work_env}`);
  if (iv.job_type) parts.push(`Job type: ${iv.job_type}`);
  if (iv.min_salary_k) parts.push(`Minimum salary: $${iv.min_salary_k}k/year`);
  if (iv.years_experience) parts.push(`Years of experience: ${iv.years_experience}`);
  if (iv.other) parts.push(`Additional: ${iv.other}`);
  return parts.join("\n");
}

function fromParsed(parsed: ParsedProfile, fallbackEmail: string): FormState {
  return {
    name: parsed.name ?? "",
    target_roles: (parsed.target_roles ?? []).join(", "),
    location_pref: parsed.location_pref ?? "",
    summary: parsed.summary ?? "",
    constraints: parsed.constraints ?? "",
    keywords: parsed.keywords ?? [],
    recipient_email: fallbackEmail,
  };
}

export default function OnboardingPage() {
  const { user, loading, getIdToken } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState<Step>("choose");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [interview, setInterview] = useState<Interview>(BLANK_INTERVIEW);
  const [form, setForm] = useState<FormState>(BLANK_FORM);
  const [parsing, setParsing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/");
  }, [user, loading, router]);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setResumeFile(file);
    setStep("interview");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleManual() {
    setResumeFile(null);
    setStep("interview");
  }

  async function handleInterviewContinue() {
    setError(null);
    if (resumeFile) {
      setParsing(true);
      try {
        const token = await getIdToken();
        if (!token) throw new Error("Not authenticated");
        const parsed = await parseResume(token, resumeFile, interviewToText(interview));
        setForm(fromParsed(parsed, user?.email ?? ""));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to parse resume");
        setParsing(false);
        return;
      } finally {
        setParsing(false);
      }
    } else {
      setForm({ ...BLANK_FORM, recipient_email: user?.email ?? "" });
    }
    setStep("form");
  }

  function setIv(field: keyof Interview) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setInterview((prev) => ({ ...prev, [field]: e.target.value }));
  }

  function set(field: keyof Omit<FormState, "keywords">) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setError("Name is required"); return; }
    if (!form.recipient_email.trim()) { setError("Report email is required"); return; }
    setSubmitting(true);
    setError(null);
    try {
      const token = await getIdToken();
      if (!token) throw new Error("Not authenticated");
      await submitOnboarding(token, {
        name: form.name.trim(),
        target_roles: form.target_roles.split(",").map((s) => s.trim()).filter(Boolean),
        location_pref: form.location_pref.trim(),
        keywords: form.keywords,
        summary: form.summary.trim(),
        constraints: form.constraints.trim(),
        recipient_email: form.recipient_email.trim(),
        interview_answers: interviewToText(interview),
        min_salary_k: interview.min_salary_k ? parseInt(interview.min_salary_k) : 0,
        years_experience: interview.years_experience ? parseInt(interview.years_experience) : 0,
        job_type: interview.job_type || "",
      });
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
      setSubmitting(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-950">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-lg font-semibold tracking-tight">Readymade.hire</h1>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-12">
        <div className="mb-8">
          <h2 className="text-2xl font-bold">Set up your job agent</h2>
          <p className="mt-1 text-sm text-gray-400">
            Tell us about yourself so we can find and score jobs for you.
          </p>
        </div>

        {/* Step 1 — Choose path */}
        {step === "choose" && (
          <div className="space-y-4">
            <input ref={fileInputRef} type="file" accept=".pdf" className="hidden" onChange={handleFileSelect} />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full text-left p-6 bg-gray-900 border border-gray-700 rounded-xl hover:border-gray-500 transition-colors"
            >
              <div className="font-semibold">Upload resume</div>
              <div className="mt-1 text-sm text-gray-400">PDF only — Claude extracts your profile and suggests keywords</div>
            </button>
            <button
              onClick={handleManual}
              className="w-full text-left p-6 bg-gray-900 border border-gray-700 rounded-xl hover:border-gray-500 transition-colors"
            >
              <div className="font-semibold">Fill in manually</div>
              <div className="mt-1 text-sm text-gray-400">Enter your profile details yourself</div>
            </button>
          </div>
        )}

        {/* Step 2 — Interview */}
        {step === "interview" && (
          <div className="space-y-6">
            {resumeFile && (
              <div className="text-xs text-gray-500 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
                Resume: <span className="text-gray-300">{resumeFile.name}</span>
              </div>
            )}

            <Field label="What type of roles are you looking for?">
              <textarea
                value={interview.roles_wanted}
                onChange={setIv("roles_wanted")}
                rows={2}
                className={inputCls}
                placeholder="e.g. Project manager, curriculum designer, construction foreman..."
              />
            </Field>

            <Field label="What industries or sectors interest you?">
              <textarea
                value={interview.industries}
                onChange={setIv("industries")}
                rows={2}
                className={inputCls}
                placeholder="e.g. Education, healthcare, real estate, tech startups..."
              />
            </Field>

            <Field label="Preferred work environment">
              <div className="flex gap-2">
                {(["Remote", "Hybrid", "In-person"] as WorkEnv[]).map((opt) => (
                  <button key={opt} type="button"
                    onClick={() => setInterview((prev) => ({ ...prev, work_env: prev.work_env === opt ? "" : opt }))}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${interview.work_env === opt ? "bg-white text-gray-900 border-white" : "bg-gray-900 text-gray-400 border-gray-700 hover:border-gray-500"}`}>
                    {opt}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Job type">
              <div className="flex gap-2 flex-wrap">
                {(["Full-time", "Contract", "Part-time", "Any"] as JobType[]).map((opt) => (
                  <button key={opt} type="button"
                    onClick={() => setInterview((prev) => ({ ...prev, job_type: prev.job_type === opt ? "" : opt }))}
                    className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${interview.job_type === opt ? "bg-white text-gray-900 border-white" : "bg-gray-900 text-gray-400 border-gray-700 hover:border-gray-500"}`}>
                    {opt}
                  </button>
                ))}
              </div>
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Minimum salary" hint="In thousands, e.g. 60 = $60k/year">
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">$</span>
                  <input type="number" min={0} step={5}
                    value={interview.min_salary_k}
                    onChange={(e) => setInterview((prev) => ({ ...prev, min_salary_k: e.target.value }))}
                    className={inputCls + " pl-7"}
                    placeholder="60" />
                </div>
              </Field>
              <Field label="Years of experience">
                <input type="number" min={0} max={50}
                  value={interview.years_experience}
                  onChange={(e) => setInterview((prev) => ({ ...prev, years_experience: e.target.value }))}
                  className={inputCls}
                  placeholder="5" />
              </Field>
            </div>

            <Field label="Anything else your agent should know?" hint="Optional — career goals, deal-breakers, things not on your resume">
              <textarea
                value={interview.other}
                onChange={setIv("other")}
                rows={3}
                className={inputCls}
                placeholder="e.g. I'm transitioning from teaching to instructional design. I want to avoid large corporations..."
              />
            </Field>

            {error && <p className="text-sm text-red-400">{error}</p>}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => { setStep("choose"); setError(null); }}
                className="px-4 py-2.5 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Back
              </button>
              <button
                onClick={handleInterviewContinue}
                disabled={parsing}
                className="flex-1 py-2.5 bg-white text-gray-900 font-medium rounded-lg hover:bg-gray-100 transition-colors text-sm disabled:opacity-50"
              >
                {parsing ? "Parsing resume with Claude..." : "Continue"}
              </button>
            </div>
          </div>
        )}

        {/* Step 3 — Profile form */}
        {step === "form" && (
          <form onSubmit={handleSubmit} className="space-y-6">
            <Field label="Full name" required>
              <input type="text" value={form.name} onChange={set("name")} required className={inputCls} placeholder="Jane Smith" />
            </Field>

            <Field label="Target roles" hint="Comma-separated — e.g. Product Manager, Operations Lead">
              <input type="text" value={form.target_roles} onChange={set("target_roles")} className={inputCls} placeholder="Software Engineer, Backend Developer" />
            </Field>

            <Field label="Location preference" hint="City or Remote">
              <input type="text" value={form.location_pref} onChange={set("location_pref")} className={inputCls} placeholder="San Francisco, CA or Remote" />
            </Field>

            <Field label="Professional summary">
              <textarea value={form.summary} onChange={set("summary")} rows={4} className={inputCls} placeholder="2–3 sentences describing your experience and what you're looking for." />
            </Field>

            <Field label="Search keywords" hint="Used to search for jobs — add, remove, or reorder">
              <KeywordTagEditor
                keywords={form.keywords}
                onChange={(kw) => setForm((prev) => ({ ...prev, keywords: kw }))}
              />
            </Field>

            <Field label="Constraints" hint="Optional — e.g. No relocation, No C2C">
              <input type="text" value={form.constraints} onChange={set("constraints")} className={inputCls} placeholder="No relocation" />
            </Field>

            <Field label="Report email" hint="Daily job reports will be sent here" required>
              <input type="email" value={form.recipient_email} onChange={set("recipient_email")} required className={inputCls} placeholder="you@example.com" />
            </Field>

            {error && <p className="text-sm text-red-400">{error}</p>}

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={() => { setStep("interview"); setError(null); }} className="px-4 py-2.5 text-sm text-gray-400 hover:text-white transition-colors">
                Back
              </button>
              <button type="submit" disabled={submitting} className="flex-1 py-2.5 bg-white text-gray-900 font-medium rounded-lg hover:bg-gray-100 transition-colors text-sm disabled:opacity-50">
                {submitting ? "Saving..." : "Start my job agent"}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}

function KeywordTagEditor({ keywords, onChange }: { keywords: string[]; onChange: (kw: string[]) => void }) {
  const [input, setInput] = useState("");

  function addKeyword(raw: string) {
    const kw = raw.trim();
    if (!kw || keywords.includes(kw)) { setInput(""); return; }
    onChange([...keywords, kw]);
    setInput("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addKeyword(input);
    } else if (e.key === "Backspace" && !input && keywords.length > 0) {
      onChange(keywords.slice(0, -1));
    }
  }

  function remove(i: number) {
    onChange(keywords.filter((_, idx) => idx !== i));
  }

  function move(i: number, dir: -1 | 1) {
    const next = [...keywords];
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {keywords.map((kw, i) => (
          <span key={i} className="flex items-center gap-1 bg-gray-800 border border-gray-700 rounded-full px-3 py-1 text-sm text-white">
            <button type="button" onClick={() => move(i, -1)} disabled={i === 0} className="text-gray-500 hover:text-white disabled:opacity-20 text-xs leading-none">↑</button>
            <button type="button" onClick={() => move(i, 1)} disabled={i === keywords.length - 1} className="text-gray-500 hover:text-white disabled:opacity-20 text-xs leading-none">↓</button>
            {kw}
            <button type="button" onClick={() => remove(i)} className="text-gray-500 hover:text-red-400 ml-1 leading-none">×</button>
          </span>
        ))}
      </div>
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => addKeyword(input)}
        className={inputCls}
        placeholder="Type a keyword and press Enter or comma to add..."
      />
    </div>
  );
}

function Field({ label, hint, required, children }: { label: string; hint?: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-200 mb-1">
        {label}{required && <span className="text-red-400 ml-1">*</span>}
      </label>
      {children}
      {hint && <p className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

const inputCls = "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-500 transition-colors";
