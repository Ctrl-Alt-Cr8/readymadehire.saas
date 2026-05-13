"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { getConfig, getRuns, triggerRun } from "@/lib/agent";
import type { RunWithJobs, Job } from "@/lib/agent";

export default function DashboardPage() {
  const { user, loading, signOut, getIdToken } = useAuth();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [runs, setRuns] = useState<RunWithJobs[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggered, setTriggered] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  // Auth + config gate
  useEffect(() => {
    if (loading) return;
    if (!user) { router.replace("/"); return; }

    getIdToken().then((token) => {
      if (!token) { router.replace("/"); return; }
      return getConfig(token);
    }).then((config) => {
      if (config === null) {
        router.replace("/onboarding");
      } else {
        setReady(true);
      }
    }).catch(() => {
      setReady(true);
    });
  }, [user, loading, router, getIdToken]);

  // Fetch run history once ready
  useEffect(() => {
    if (!ready) return;
    getIdToken().then((token) => {
      if (!token) return;
      return getRuns(token);
    }).then((data) => {
      const list = data ?? [];
      setRuns(list);
      if (list.length > 0) setExpanded(list[0].id);
    }).catch((err) => {
      setFetchError(err instanceof Error ? err.message : "Failed to load runs");
    }).finally(() => {
      setRunsLoading(false);
    });
  }, [ready, getIdToken]);

  async function handleRunAgent() {
    setTriggering(true);
    setTriggerError(null);
    try {
      const token = await getIdToken();
      if (!token) return;
      await triggerRun(token);
      setTriggered(true);
    } catch (err) {
      setTriggerError(err instanceof Error ? err.message : "Failed to start agent");
    } finally {
      setTriggering(false);
    }
  }

  if (loading || !user || !ready) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-950">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Readymade.hire</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-400">{user.email}</span>
          <button
            onClick={signOut}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-8">
        {/* Run Agent */}
        <div className="flex flex-col gap-2">
          {triggered ? (
            <div className="rounded-xl bg-gray-900 border border-gray-700 px-5 py-4 text-sm text-gray-300">
              Agent is running — this takes a few minutes. Refresh the page when done to see results.
            </div>
          ) : (
            <button
              onClick={handleRunAgent}
              disabled={triggering}
              className="self-start px-5 py-2.5 bg-white text-gray-900 font-medium rounded-lg hover:bg-gray-100 transition-colors text-sm disabled:opacity-50"
            >
              {triggering ? "Starting..." : "Run Agent"}
            </button>
          )}
          {triggerError && (
            <p className="text-sm text-red-400">{triggerError}</p>
          )}
        </div>

        {/* Run history */}
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Run history</h2>

          {runsLoading && (
            <div className="text-sm text-gray-500">Loading...</div>
          )}

          {!runsLoading && fetchError && (
            <div className="text-sm text-red-400">{fetchError}</div>
          )}

          {!runsLoading && !fetchError && runs.length === 0 && (
            <div className="rounded-xl bg-gray-900 border border-gray-800 px-5 py-8 text-center text-sm text-gray-500">
              No runs yet. Hit <span className="text-white font-medium">Run Agent</span> to start your first job search.
            </div>
          )}

          {runs.map((run) => (
            <RunCard
              key={run.id}
              run={run}
              expanded={expanded === run.id}
              onToggle={() => setExpanded(expanded === run.id ? null : run.id)}
            />
          ))}
        </div>
      </main>
    </div>
  );
}

function RunCard({
  run,
  expanded,
  onToggle,
}: {
  run: RunWithJobs;
  expanded: boolean;
  onToggle: () => void;
}) {
  const date = new Date(run.run_at);
  const dateStr = date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  const timeStr = date.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

  return (
    <div className="rounded-xl bg-gray-900 border border-gray-800 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full text-left px-5 py-4 hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-white">
              {dateStr} <span className="text-gray-500 font-normal">at {timeStr}</span>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
              <span>{run.jobs_fetched ?? "—"} fetched</span>
              <span className="text-green-400">{run.jobs_apply} APPLY</span>
              <span className="text-amber-400">{run.jobs_review} REVIEW</span>
              <span className="text-gray-500">{run.jobs_skip} SKIP</span>
              <span className="text-gray-500">${run.estimated_cost.toFixed(4)}</span>
            </div>
          </div>
          <span className="text-gray-500 text-xs mt-0.5 shrink-0">
            {expanded ? "▲" : "▼"} {run.jobs.length} jobs
          </span>
        </div>
      </button>

      {expanded && run.jobs.length > 0 && (
        <div className="border-t border-gray-800 divide-y divide-gray-800/60">
          {run.jobs.map((job) => (
            <JobRow key={job.id} job={job} />
          ))}
        </div>
      )}

      {expanded && run.jobs.length === 0 && (
        <div className="border-t border-gray-800 px-5 py-4 text-sm text-gray-500">
          No jobs recorded for this run.
        </div>
      )}
    </div>
  );
}

function JobRow({ job }: { job: Job }) {
  const badge: Record<string, string> = {
    APPLY: "bg-green-500/15 text-green-400 border border-green-500/25",
    REVIEW: "bg-amber-500/15 text-amber-400 border border-amber-500/25",
    SKIP: "bg-gray-500/15 text-gray-500 border border-gray-500/25",
  };

  const inner = (
    <div className="px-5 py-3 flex items-center gap-3">
      <span className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide ${badge[job.decision] ?? badge.SKIP}`}>
        {job.decision}
      </span>
      <div className="flex-1 min-w-0">
        <span className="text-sm text-white truncate block">{job.title}</span>
        <span className="text-xs text-gray-500">{job.company || "—"}</span>
      </div>
      <span className="shrink-0 text-xs text-gray-500 tabular-nums">{job.score}</span>
    </div>
  );

  if (job.url) {
    return (
      <a href={job.url} target="_blank" rel="noopener noreferrer"
        className="block hover:bg-gray-800/40 transition-colors">
        {inner}
      </a>
    );
  }
  return <div>{inner}</div>;
}
