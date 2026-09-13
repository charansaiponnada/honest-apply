import { useMemo, useState } from "react"
import { toast } from "sonner"

import { api, streamEvents } from "@/app/api"
import type { BatchSummaryItem, Job, PipelineEvent, RecommendedJob, RunResult } from "@/app/types"
import { OUTCOMES } from "@/app/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"

interface BatchRow {
  key: string
  title: string
  status: string
  runId?: string
}

export function RecommendationsCard({
  resume,
  github,
  userId,
  slackChannel,
  onUseJob,
  onEvent,
  onResult,
  onShowResult,
}: {
  resume: string
  github: string
  userId: string
  slackChannel: string
  onUseJob: (job: Job) => void
  onEvent: (event: PipelineEvent) => void
  onResult: (result: RunResult) => void
  onShowResult: (runId: string) => void
}) {
  const [jobs, setJobs] = useState<RecommendedJob[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [hint, setHint] = useState("Ranks live jobs by how many of your proven skills they ask for (resume + GitHub).")
  const [matching, setMatching] = useState(false)
  const [applying, setApplying] = useState(false)
  const [batch, setBatch] = useState<BatchRow[]>([])

  async function findMatches() {
    setMatching(true)
    try {
      const res = await api<{ jobs: RecommendedJob[]; pool_size: number; error: string | null; github_error: string | null }>(
        "/api/recommendations",
        { body: { resume_text: resume, github_username: github, limit: 10 } },
      )
      setJobs(res.jobs)
      setSelected(new Set(res.jobs.flatMap((j, i) => (i < 3 && !j.senior_role ? [i] : []))))
      setHint(
        res.jobs.length
          ? `Top ${res.jobs.length} of ${res.pool_size} live listings.${res.github_error ? ` GitHub: ${res.github_error}` : ""}`
          : (res.error ?? "No live listings mention your skills right now."),
      )
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setMatching(false)
    }
  }

  async function applySelected() {
    const picks = [...selected].sort((a, b) => a - b).map((i) => jobs[i])
    const rows: BatchRow[] = picks.map((j, i) => ({ key: `${i}-${j.url}`, title: `${j.title} — ${j.company_name}`, status: "queued" }))
    setBatch(rows)
    setApplying(true)
    let current = -1
    const update = (index: number, patch: Partial<BatchRow>) =>
      setBatch((prev) => prev.map((row, i) => (i === index ? { ...row, ...patch } : row)))
    try {
      await streamEvents(
        "/api/apply-batch",
        {
          resume_text: resume,
          jobs: picks.map((j) => ({ title: j.title, company_name: j.company_name, description: j.description || j.title, url: j.url })),
          user_id: userId,
          slack_channel: slackChannel,
          github_username: github,
        },
        (event) => {
          if (event.type === "batch") {
            current = event.index - 1
            update(current, { status: "running" })
          } else if (event.type === "result") {
            update(current, { status: event.result.outcome, runId: event.result.run_id })
            onResult(event.result)
          } else if (event.type === "batch_done") {
            event.summary.forEach((item: BatchSummaryItem, i) => {
              if (item.outcome === "error") update(i, { status: "error" })
            })
            const drafted = event.summary.filter((s) => s.outcome === "drafted" || s.outcome === "sent").length
            toast.success(`${drafted} drafted, ${event.summary.length - drafted} stopped by a gate or error. Undo any run from the Tracker.`)
          }
          onEvent(event)
        },
      )
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setApplying(false)
    }
  }

  const count = selected.size

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recommended for you</CardTitle>
        <CardDescription>{hint}</CardDescription>
        <CardAction className="flex gap-2">
          <Button variant="outline" size="sm" disabled={matching || resume.trim().length < 20} onClick={findMatches}>
            {matching ? <Spinner data-icon="inline-start" /> : null}
            Find matches
          </Button>
          <Button size="sm" disabled={applying || count === 0 || count > 5} onClick={applySelected}>
            {applying ? <Spinner data-icon="inline-start" /> : null}
            {count > 5 ? "Select up to 5" : `Apply to selected (${count})`}
          </Button>
        </CardAction>
      </CardHeader>
      {jobs.length || batch.length ? (
        <CardContent className="flex flex-col gap-3">
          {jobs.map((job, i) => (
            <div key={`${job.url}-${i}`} className="flex items-start gap-3 text-sm">
              <Checkbox
                id={`rec-${i}`}
                checked={selected.has(i)}
                onCheckedChange={(checked: boolean) =>
                  setSelected((prev) => {
                    const next = new Set(prev)
                    if (checked) next.add(i)
                    else next.delete(i)
                    return next
                  })
                }
              />
              <label htmlFor={`rec-${i}`} className="flex min-w-0 flex-1 cursor-pointer flex-col gap-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{job.title}</span>
                  <span className="text-muted-foreground">— {job.company_name}</span>
                  {job.senior_role ? <Badge variant="outline">senior role</Badge> : null}
                </span>
                <span className="text-xs text-muted-foreground">
                  Matches {job.matched_skills.length} resume skills: {job.matched_skills.slice(0, 6).join(", ") || "—"}
                  {job.github_skills.length ? ` · from GitHub: ${job.github_skills.slice(0, 4).join(", ")}` : ""}
                </span>
              </label>
              <Button variant="ghost" size="sm" onClick={() => onUseJob(job)}>
                Use
              </Button>
            </div>
          ))}
          {batch.length ? (
            <div className="flex flex-col gap-2">
              <Separator />
              <span className="text-xs font-medium text-muted-foreground">Applying one by one: drafts only, every gate on</span>
              {batch.map((row) => {
                const outcome = OUTCOMES[row.status as keyof typeof OUTCOMES]
                return (
                  <div key={row.key} className="flex flex-wrap items-center gap-2 text-sm">
                    <Badge variant={outcome?.variant ?? (row.status === "error" ? "destructive" : "outline")}>
                      {row.status === "running" ? <Spinner data-icon="inline-start" /> : null}
                      {outcome?.label ?? row.status}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate">{row.title}</span>
                    {row.runId ? (
                      <Button variant="outline" size="sm" onClick={() => onShowResult(row.runId!)}>
                        View
                      </Button>
                    ) : null}
                  </div>
                )
              })}
            </div>
          ) : null}
        </CardContent>
      ) : null}
    </Card>
  )
}

export function LiveJobsCard({ onUseJob }: { onUseJob: (job: Job) => void }) {
  const [pool, setPool] = useState<Job[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState("")

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (pool ?? []).filter(
      (j) => !q || `${j.title} ${j.company_name} ${j.location ?? ""} ${(j.tags ?? []).join(" ")}`.toLowerCase().includes(q),
    )
  }, [pool, query])

  async function load() {
    setLoading(true)
    try {
      const res = await api<{ jobs: Job[]; error: string | null }>("/api/jobs?limit=60")
      setPool(res.jobs)
      setError(res.error)
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Find a live job</CardTitle>
        <CardDescription>{error ?? "Arbeitnow, Remotive and RemoteOK. Public APIs, no scraping."}</CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" disabled={loading} onClick={load}>
            {loading ? <Spinner data-icon="inline-start" /> : null}
            {pool ? "Refresh" : "Load listings"}
          </Button>
        </CardAction>
      </CardHeader>
      {pool ? (
        <CardContent className="flex flex-col gap-3">
          <Input type="search" placeholder="Filter by role, skill, company" aria-label="Filter jobs" value={query} onChange={(e) => setQuery(e.target.value)} />
          <span className="text-xs text-muted-foreground">{matches.length} listings</span>
          <ScrollArea className="h-64">
            <div className="flex flex-col gap-2 pr-3">
              {matches.slice(0, 40).map((job, i) => (
                <div key={`${job.url}-${i}`} className="flex items-center gap-3 text-sm">
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate">
                      <span className="font-medium">{job.title}</span> — {job.company_name}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {[job.source, job.location, job.posted].filter(Boolean).join(" · ")}
                    </span>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => onUseJob(job)}>
                    Use
                  </Button>
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      ) : null}
    </Card>
  )
}
