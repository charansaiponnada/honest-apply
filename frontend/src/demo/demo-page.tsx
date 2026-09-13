import type { LucideIcon } from "lucide-react"
import {
  ArrowRight,
  CircleCheck,
  FlaskConical,
  LayoutDashboard,
  MailCheck,
  Moon,
  Play,
  ShieldAlert,
  ShieldCheck,
  Sun,
  Undo2,
} from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import { api, store, streamEvents } from "@/app/api"
import { PipelineCard, usePipeline } from "@/app/pipeline"
import { ResultView } from "@/app/result-view"
import type { AppKey, Connections, EvalSummary, HistoryRow, RunResult } from "@/app/types"
import { APP_LABELS, OUTCOMES } from "@/app/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"

type Scenario = { company: string; role: string; jd_text: string }
type SceneId = "fit" | "reply" | "bait" | "chaos" | "undo"
type StepResults = Record<string, { status: string; detail: string }>

const APPS: AppKey[] = ["gmail", "calendar", "crm", "slack"]

const SCENES: { id: SceneId; icon: LucideIcon; title: string; text: string }[] = [
  { id: "fit", icon: Play, title: "A strong fit acts in four apps", text: "Three agents tailor the sample resume with receipts, then Gmail → Calendar → HubSpot → Slack, each handing its link to the next." },
  { id: "reply", icon: MailCheck, title: "The employer replies", text: "The HubSpot deal moves to Replied, the follow-up reminder is cancelled, and Slack pings you." },
  { id: "bait", icon: ShieldAlert, title: "A job that baits fabrication", text: "It demands Terraform, GCP, Go and a certification the resume doesn't have. The gates stop it: nothing is sent, and the gaps are shown." },
  { id: "chaos", icon: FlaskConical, title: "Gmail goes down mid-run", text: "The chaos panel breaks Gmail on purpose. The agent retries, reports a clear reason, finishes the other apps and ends as partial, not a crash." },
  { id: "undo", icon: Undo2, title: "Undo everything", text: "One click deletes the draft and reminder, closes the CRM deal and tells Slack, across every app the first run touched." },
]

function Kpi({ label, value, hint, tone }: { label: string; value?: string; hint: string; tone: "emerald" | "yellow" }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        {value === undefined ? (
          <Skeleton className="h-10 w-20" />
        ) : (
          <CardTitle className={`text-4xl font-bold tabular-nums ${tone === "emerald" ? "text-kpi-emerald" : "text-kpi-yellow"}`}>{value}</CardTitle>
        )}
      </CardHeader>
      <CardContent className="text-xs text-muted-foreground">{hint}</CardContent>
    </Card>
  )
}

function StepBadges({ results }: { results?: StepResults }) {
  if (!results) return null
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(results).map(([app, r]) => (
        <Badge key={app} variant={r.status === "ok" || r.status === "mocked" ? "default" : r.status === "skipped" ? "outline" : "destructive"} title={r.detail}>
          {APP_LABELS[app as AppKey] ?? app}: {r.status}
        </Badge>
      ))}
    </div>
  )
}

export function DemoPage() {
  const [theme, setTheme] = useState<"dark" | "light">(() => (store.get("demoTheme") === "light" ? "light" : "dark"))
  const [resume, setResume] = useState("")
  const [scenarios, setScenarios] = useState<Record<"good_fit" | "bait", Scenario> | null>(null)
  const [connections, setConnections] = useState<Connections | null>(null)
  const [history, setHistory] = useState<HistoryRow[] | null>(null)
  const [summary, setSummary] = useState<{ normal?: EvalSummary; faults?: EvalSummary } | null>(null)
  const [busy, setBusy] = useState<SceneId | null>(null)
  const [runs, setRuns] = useState<Partial<Record<"fit" | "bait" | "chaos", RunResult>>>({})
  const [steps, setSteps] = useState<Partial<Record<"reply" | "undo", StepResults>>>({})
  const [selected, setSelected] = useState<"fit" | "bait" | "chaos" | null>(null)
  const pipeline = usePipeline()
  const profile = { userId: store.get("userId"), slackChannel: store.get("slackChannel"), github: store.get("github") }

  const reload = useCallback(() => {
    api<HistoryRow[]>("/api/history").then(setHistory).catch(() => setHistory([]))
    api<{ normal?: EvalSummary; faults?: EvalSummary }>("/api/eval/summary").then(setSummary).catch(() => setSummary({}))
  }, [])

  useEffect(() => {
    document.title = "Live demo · Honest Apply"
    api<{ resume: string }>("/api/defaults").then((d) => setResume(d.resume)).catch((err: Error) => toast.error(err.message))
    api<Record<"good_fit" | "bait", Scenario>>("/api/demo/scenarios").then(setScenarios).catch((err: Error) => toast.error(err.message))
    api<Connections>(`/api/connections?user_id=${encodeURIComponent(store.get("userId"))}`).then(setConnections).catch(() => undefined)
    reload()
  }, [reload])

  useEffect(() => store.set("demoTheme", theme), [theme])

  async function runScenario(key: "good_fit" | "bait", faults?: string[]) {
    const scenario = scenarios?.[key]
    if (!scenario || !resume) return null
    pipeline.reset()
    const box: { result: RunResult | null } = { result: null }
    try {
      if (faults) await api("/api/faults", { body: { faults } })
      await streamEvents(
        "/api/run",
        {
          resume_text: resume,
          jd_text: scenario.jd_text,
          company: scenario.company,
          role: scenario.role,
          jd_source: `demo: ${key}`,
          user_id: profile.userId,
          slack_channel: profile.slackChannel,
          github_username: profile.github,
          allow_duplicate: true,
        },
        (event) => {
          pipeline.handle(event)
          if (event.type === "result") box.result = event.result
          if (event.type === "error") toast.error(event.detail)
        },
      )
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      if (faults) await api("/api/faults", { body: { faults: [] } }).catch(() => undefined)
    }
    return box.result
  }

  async function play(scene: SceneId) {
    setBusy(scene)
    try {
      if (scene === "fit" || scene === "bait" || scene === "chaos") {
        const result = await runScenario(scene === "bait" ? "bait" : "good_fit", scene === "chaos" ? ["gmail"] : undefined)
        if (result) {
          setRuns((r) => ({ ...r, [scene]: result }))
          setSelected(scene)
          if (scene === "fit") setSteps({})
        }
      } else if (scene === "reply" && runs.fit) {
        const res = await api<{ replies: { run_id: string; results?: StepResults; error?: string }[] }>(
          `/api/replies/simulate/${encodeURIComponent(runs.fit.run_id)}`,
          { method: "POST" },
        )
        const mine = res.replies.find((r) => r.run_id === runs.fit?.run_id)
        if (mine?.results) setSteps((s) => ({ ...s, reply: mine.results }))
        else toast.info(mine?.error ?? "That run already has a reply. Run step 1 again for a fresh one.")
      } else if (scene === "undo" && runs.fit) {
        const res = await api<{ already_undone: boolean; results: StepResults }>(`/api/undo/${encodeURIComponent(runs.fit.run_id)}`, { method: "POST" })
        if (res.already_undone) toast.info("Already undone. Run step 1 again for a fresh run.")
        setSteps((s) => ({ ...s, undo: res.results }))
      }
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(null)
      reload()
    }
  }

  const active = history?.filter((r) => !r.undone)
  const fitActions = runs.fit ? Object.values(runs.fit.actions).filter((a) => a.status === "ok" || a.status === "mocked").length : undefined
  const needsFit = (scene: SceneId) => (scene === "reply" || scene === "undo") && !runs.fit
  const sceneOutcome = (scene: SceneId) => {
    if (scene === "fit" || scene === "bait" || scene === "chaos") {
      const r = runs[scene]
      return r ? OUTCOMES[r.outcome] : undefined
    }
    return steps[scene] ? { label: scene === "reply" ? "Loop closed" : "Reversed", variant: "default" as const } : undefined
  }
  const selectedRun = selected ? runs[selected] : undefined

  return (
    <div className={`${theme === "dark" ? "demo-theme-dark" : "demo-theme-light"} min-h-svh bg-background text-foreground`}>
      <header className="sticky top-0 z-10 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck aria-hidden="true" />
            </span>
            Honest Apply
          </a>
          <Badge variant="secondary">Live demo</Badge>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {APPS.map((app) => (
              <Badge key={app} variant={connections?.apps[app].connected ? "default" : "outline"}>
                {APP_LABELS[app]}
              </Badge>
            ))}
            <Button variant="outline" size="icon" aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun /> : <Moon />}
            </Button>
            <Button variant="outline" size="sm" nativeButton={false} render={<a href="/app" />}>
              <LayoutDashboard data-icon="inline-start" />
              Dashboard
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Everything the agent does, in five steps.</h1>
          <p className="max-w-3xl text-muted-foreground">
            Uses the sample resume and two fixed job posts from the test set, so every run is repeatable. Connected apps act for real.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi tone="emerald" label="Apps acted in (step 1)" value={fitActions === undefined ? "—" : `${fitActions}/4`} hint="Gmail, Calendar, HubSpot and Slack" />
          <Kpi tone="emerald" label="Drafted or sent" value={active?.filter((r) => r.outcome === "drafted" || r.outcome === "sent").length.toString()} hint="Applications that passed every gate" />
          <Kpi tone="yellow" label="Stopped by a gate" value={history?.filter((r) => r.outcome === "flagged" || r.outcome === "duplicate").length.toString()} hint="Nothing sent; Slack told you why" />
          <Kpi tone="emerald" label="Test suite" value={summary === null ? undefined : summary.normal ? `${summary.normal.passed}/${summary.normal.total}` : "—"} hint={summary?.faults ? `${summary.faults.passed}/${summary.faults.total} with Gmail down + LLM 429` : "10 job descriptions, 4 checks"} />
        </div>

        {!profile.slackChannel ? (
          <Alert>
            <AlertTitle>Slack will post to #general</AlertTitle>
            <AlertDescription>Set a channel under Apps &amp; profile in the dashboard before recording.</AlertDescription>
          </Alert>
        ) : null}

        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,26rem)_1fr]">
          <div className="flex flex-col gap-4">
            {SCENES.map((scene, i) => {
              const outcome = sceneOutcome(scene.id)
              const disabled = busy !== null || !scenarios || !resume || needsFit(scene.id)
              return (
                <Card key={scene.id} className={selected === scene.id ? "ring-2 ring-primary" : undefined}>
                  <CardHeader>
                    <CardDescription className="flex items-center gap-2">
                      <scene.icon aria-hidden="true" />
                      Step {i + 1}
                    </CardDescription>
                    <CardTitle>{scene.title}</CardTitle>
                    <CardAction>
                      <Button size="sm" disabled={disabled} onClick={() => void play(scene.id)}>
                        {busy === scene.id ? <Spinner data-icon="inline-start" /> : outcome ? <CircleCheck data-icon="inline-start" /> : <Play data-icon="inline-start" />}
                        {outcome ? "Again" : "Run"}
                      </Button>
                    </CardAction>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3 text-sm">
                    <p className="leading-relaxed text-muted-foreground">{scene.text}</p>
                    {needsFit(scene.id) ? <span className="text-xs text-kpi-yellow">Run step 1 first.</span> : null}
                    {outcome ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={outcome.variant}>{outcome.label}</Badge>
                        {scene.id === "fit" || scene.id === "bait" || scene.id === "chaos" ? (
                          <Button variant="ghost" size="sm" onClick={() => setSelected(scene.id as "fit" | "bait" | "chaos")}>
                            View result
                            <ArrowRight data-icon="inline-end" />
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                    {scene.id === "reply" || scene.id === "undo" ? <StepBadges results={steps[scene.id]} /> : null}
                  </CardContent>
                </Card>
              )
            })}
          </div>

          <div className="flex min-w-0 flex-col gap-6">
            <PipelineCard state={pipeline.state} />
            {selectedRun ? (
              <ResultView key={selectedRun.run_id} result={selectedRun} onUndo={async (runId) => {
                try {
                  await api(`/api/undo/${encodeURIComponent(runId)}`, { method: "POST" })
                  toast.success("Undone across every app.")
                  reload()
                  return true
                } catch (err) {
                  toast.error((err as Error).message)
                  return false
                }
              }} />
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Results appear here</CardTitle>
                  <CardDescription>Start with step 1. Each step streams through the live pipeline above.</CardDescription>
                </CardHeader>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
