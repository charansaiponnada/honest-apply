import type { LucideIcon } from "lucide-react"
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CalendarClock,
  FileSearch,
  FlaskConical,
  LayoutDashboard,
  Mail,
  MailCheck,
  MessageSquare,
  Moon,
  PenLine,
  Play,
  ShieldAlert,
  ShieldCheck,
  Sun,
  Undo2,
} from "lucide-react"
import type { ReactNode } from "react"
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import { api, pct, safeUrl, store, streamEvents } from "@/app/api"
import { PipelineCard, usePipeline } from "@/app/pipeline"
import { Gaps, Receipts } from "@/app/result-view"
import type { AppKey, Connections, EvalSummary, HistoryRow, RunResult } from "@/app/types"
import { APP_LABELS, OUTCOMES } from "@/app/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"

type Scenario = { company: string; role: string; jd_text: string }
type StepResults = Record<string, { status: string; detail: string }>
type RunKey = "fit" | "bait" | "chaos"

const SCREENS = ["intro", "connect", "job", "agents", "receipts", "apps", "reply", "bait", "chaos", "undo", "proof"] as const
type ScreenId = (typeof SCREENS)[number]

const SCREEN_LABELS: Record<ScreenId, string> = {
  intro: "Intro",
  connect: "Connect apps",
  job: "The job",
  agents: "Agents at work",
  receipts: "Receipts",
  apps: "Apps hand off",
  reply: "They reply",
  bait: "Honesty gate",
  chaos: "Chaos test",
  undo: "Undo",
  proof: "Proof",
}

const APPS: AppKey[] = ["gmail", "calendar", "crm", "slack"]

const APP_META: Record<AppKey, { icon: LucideIcon; name: string; role: string }> = {
  gmail: { icon: Mail, name: "Gmail", role: "Drafts the application email with your tailored resume." },
  calendar: { icon: CalendarClock, name: "Google Calendar", role: "Books a follow-up in 7 days, linked to that email." },
  crm: { icon: Building2, name: "HubSpot CRM", role: "Creates a deal for the employer and candidate, carrying both links." },
  slack: { icon: MessageSquare, name: "Slack", role: "Posts one message with every link, or why it stopped." },
}

const AGENTS: { icon: LucideIcon; name: string; text: string }[] = [
  { icon: FileSearch, name: "Researcher", text: "Reads the job post and pulls out skills, seniority and must-haves." },
  { icon: PenLine, name: "Tailor", text: "Rewrites the resume from lines you already have, citing each source line." },
  { icon: ShieldCheck, name: "Executor", text: "Checks every receipt in code, then chooses which apps to act in." },
]

function initialScreen(): ScreenId {
  const hash = window.location.hash.slice(1)
  return (SCREENS as readonly string[]).includes(hash) ? (hash as ScreenId) : "intro"
}

function IconTile({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-secondary text-primary">
      <Icon aria-hidden="true" />
    </span>
  )
}

function Screen({ eyebrow, title, description, children }: { eyebrow: string; title: string; description?: string; children: ReactNode }) {
  return (
    <section className="mx-auto flex w-full max-w-5xl animate-in flex-col gap-8 duration-300 fade-in slide-in-from-bottom-2 motion-reduce:animate-none">
      <div className="flex flex-col gap-3">
        <Badge variant="secondary" className="w-fit">
          {eyebrow}
        </Badge>
        <h1 className="text-3xl font-bold tracking-tight text-balance sm:text-5xl">{title}</h1>
        {description ? <p className="max-w-3xl text-lg leading-relaxed text-pretty text-muted-foreground">{description}</p> : null}
      </div>
      {children}
    </section>
  )
}

const statusVariant = (status?: string) =>
  status === "ok" || status === "mocked" ? "default" : status === "skipped" || !status ? "outline" : "destructive"

function StepResultCards({ results, labels }: { results: StepResults; labels: Partial<Record<string, string>> }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Object.entries(results).map(([app, r]) => {
        const meta = APP_META[app as AppKey]
        return (
          <Card key={app}>
            <CardHeader>
              {meta ? <IconTile icon={meta.icon} /> : null}
              <CardTitle>{labels[app] ?? APP_LABELS[app as AppKey] ?? app}</CardTitle>
              <CardDescription className="leading-relaxed">{r.detail}</CardDescription>
            </CardHeader>
            <CardFooter>
              <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
            </CardFooter>
          </Card>
        )
      })}
    </div>
  )
}

function Kpi({ label, value, hint, tone }: { label: string; value: string; hint: string; tone: "emerald" | "yellow" }) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className={`text-5xl font-bold tabular-nums ${tone === "emerald" ? "text-kpi-emerald" : "text-kpi-yellow"}`}>{value}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">{hint}</CardContent>
    </Card>
  )
}

export function DemoPage() {
  const [theme, setTheme] = useState<"dark" | "light">(() => (store.get("demoTheme") === "light" ? "light" : "dark"))
  const [screen, setScreen] = useState<ScreenId>(initialScreen)
  // Simulated by default: anyone (including judges) can run every step with no accounts or keys.
  const [simulate, setSimulate] = useState(() => store.get("demoMode") !== "live")
  const [userId, setUserId] = useState(() => store.get("userId"))
  const [slackChannel, setSlackChannel] = useState(() => store.get("slackChannel"))
  const [resume, setResume] = useState("")
  const [scenarios, setScenarios] = useState<Record<"good_fit" | "bait", Scenario> | null>(null)
  const [connections, setConnections] = useState<Connections | null>(null)
  const [history, setHistory] = useState<HistoryRow[]>([])
  const [summary, setSummary] = useState<{ normal?: EvalSummary; faults?: EvalSummary }>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [runs, setRuns] = useState<Partial<Record<RunKey, RunResult>>>({})
  const [steps, setSteps] = useState<Partial<Record<"reply" | "undo", StepResults>>>({})
  const pipeline = usePipeline()
  const index = SCREENS.indexOf(screen)

  const goTo = useCallback((next: ScreenId) => {
    setScreen(next)
    window.history.replaceState(null, "", `/demo#${next}`)
    window.scrollTo({ top: 0 })
  }, [])

  const reload = useCallback(() => {
    api<HistoryRow[]>("/api/history").then(setHistory).catch(() => undefined)
    api<{ normal?: EvalSummary; faults?: EvalSummary }>("/api/eval/summary").then(setSummary).catch(() => undefined)
  }, [])

  useEffect(() => {
    document.title = "Live demo · Honest Apply"
    api<{ resume: string }>("/api/defaults").then((d) => setResume(d.resume)).catch((err: Error) => toast.error(err.message))
    api<Record<"good_fit" | "bait", Scenario>>("/api/demo/scenarios").then(setScenarios).catch((err: Error) => toast.error(err.message))
    reload()
    const connected = new URLSearchParams(window.location.search).get("connected")
    if (connected) {
      toast.success(`${APP_LABELS[connected as AppKey] ?? "App"} connected.`)
      setScreen("connect")
      window.history.replaceState(null, "", "/demo#connect")
    }
  }, [reload])

  useEffect(() => store.set("demoTheme", theme), [theme])
  useEffect(() => store.set("demoMode", simulate ? "simulated" : "live"), [simulate])

  useEffect(() => {
    store.set("userId", userId)
    store.set("slackChannel", slackChannel)
    const timer = setTimeout(() => {
      api<Connections>(`/api/connections?user_id=${encodeURIComponent(userId)}`).then(setConnections).catch(() => undefined)
    }, 400)
    return () => clearTimeout(timer)
  }, [userId, slackChannel])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest("input, textarea, [contenteditable='true']")) return
      if (event.key === "ArrowRight" && index < SCREENS.length - 1) goTo(SCREENS[index + 1])
      if (event.key === "ArrowLeft" && index > 0) goTo(SCREENS[index - 1])
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [index, goTo])

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
          user_id: userId,
          slack_channel: slackChannel,
          github_username: store.get("github"),
          allow_duplicate: true,
          simulate,
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

  async function play(step: RunKey | "reply" | "undo") {
    setBusy(step)
    try {
      if (step === "fit" || step === "bait" || step === "chaos") {
        const result = await runScenario(step === "bait" ? "bait" : "good_fit", step === "chaos" ? ["gmail"] : undefined)
        if (result) {
          setRuns((r) => ({ ...r, [step]: result }))
          if (step === "fit") setSteps({})
        }
      } else if (step === "reply" && runs.fit) {
        const res = await api<{ replies: { run_id: string; results?: StepResults; error?: string }[] }>(
          `/api/replies/simulate/${encodeURIComponent(runs.fit.run_id)}`,
          { method: "POST" },
        )
        const mine = res.replies.find((r) => r.run_id === runs.fit?.run_id)
        if (mine?.results) setSteps((s) => ({ ...s, reply: mine.results }))
        else toast.info(mine?.error ?? "That application already has a reply. Run the job again for a fresh one.")
      } else if (step === "undo" && runs.fit) {
        const res = await api<{ already_undone: boolean; results: StepResults }>(`/api/undo/${encodeURIComponent(runs.fit.run_id)}`, { method: "POST" })
        if (res.already_undone) toast.info("Already undone. Run the job again for a fresh application.")
        setSteps((s) => ({ ...s, undo: res.results }))
      }
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(null)
      reload()
    }
  }

  function startFit() {
    goTo("agents")
    void play("fit")
  }

  const runButton = (label: string, step: RunKey | "reply" | "undo", icon: LucideIcon, onClick?: () => void) => {
    const Icon = icon
    const needsFit = (step === "reply" || step === "undo") && !runs.fit
    return (
      <Button size="lg" className="w-fit" disabled={busy !== null || !scenarios || !resume || needsFit} onClick={onClick ?? (() => void play(step))}>
        {busy === step ? <Spinner data-icon="inline-start" /> : <Icon data-icon="inline-start" />}
        {label}
      </Button>
    )
  }

  const needsFitNotice = (
    <Alert>
      <AlertTitle>Run the job first</AlertTitle>
      <AlertDescription className="flex flex-wrap items-center gap-2">
        This step uses the application from "The job".
        <Button variant="link" className="h-auto p-0" onClick={() => goTo("job")}>
          Go to the job
        </Button>
      </AlertDescription>
    </Alert>
  )

  const fit = runs.fit
  const fitOutcome = fit ? OUTCOMES[fit.outcome] : undefined
  const job = scenarios?.good_fit
  const appState = (app: AppKey) => {
    if (simulate) return "Simulated"
    const a = connections?.apps[app]
    return a?.via === "composio" ? "Connected" : a?.via === "env" ? "Server keys" : "Not connected"
  }

  async function connect(app: AppKey) {
    setBusy(`connect-${app}`)
    try {
      const { redirect_url: url } = await api<{ redirect_url: string }>(`/api/connections/${app}/link`, { body: { user_id: userId, return_to: "demo" } })
      const safe = safeUrl(url)
      if (safe) window.location.href = safe
      else toast.error("Composio did not return a connect link.")
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  function renderScreen() {
    switch (screen) {
      case "intro":
        return (
          <Screen
            eyebrow="Honest Apply · live demo"
            title="The job agent that won't lie for you."
            description="Three agents tailor real experience to a job, prove every line, then act across Gmail, Google Calendar, HubSpot and Slack. Here's the whole flow, one screen at a time."
          >
            <div className="grid gap-4 sm:grid-cols-3">
              {AGENTS.map((agent) => (
                <Card key={agent.name}>
                  <CardHeader>
                    <IconTile icon={agent.icon} />
                    <CardTitle>{agent.name}</CardTitle>
                    <CardDescription className="leading-relaxed">{agent.text}</CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {APPS.map((app, i) => (
                <div key={app} className="flex items-center gap-3">
                  <Badge className="h-8 px-3 text-sm">{APP_META[app].name}</Badge>
                  {i < APPS.length - 1 ? <ArrowRight className="text-muted-foreground" aria-hidden="true" /> : null}
                </div>
              ))}
            </div>
            <Button size="lg" className="w-fit" onClick={() => goTo("connect")}>
              Start
              <ArrowRight data-icon="inline-end" />
            </Button>
          </Screen>
        )

      case "connect":
        return (
          <Screen
            eyebrow="Step 1 · Connect"
            title="Your own apps, connected in one click."
            description="Composio handles each sign-in and stores the tokens. The agent acts on these accounts, and each app hands its output to the next."
          >
            {simulate ? (
              <Alert>
                <AlertTitle>Simulated mode</AlertTitle>
                <AlertDescription>
                  Every step runs with no accounts or keys: the apps are simulated on the server and marked as mock, so anyone can
                  reproduce this demo from the repo. Turn on Live apps in the header to act on your connected accounts.
                </AlertDescription>
              </Alert>
            ) : null}
            <FieldGroup className="grid gap-4 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="demo-user">Your email</FieldLabel>
                <Input id="demo-user" type="email" placeholder="you@example.com" value={userId} onChange={(e) => setUserId(e.target.value.trim())} />
              </Field>
              <Field>
                <FieldLabel htmlFor="demo-slack">Slack channel</FieldLabel>
                <Input id="demo-slack" placeholder="#job-applications" value={slackChannel} onChange={(e) => setSlackChannel(e.target.value.trim())} />
                <FieldDescription>{slackChannel ? "Posts go here." : "Empty means #general."}</FieldDescription>
              </Field>
            </FieldGroup>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {APPS.map((app) => {
                const meta = APP_META[app]
                const state = connections?.apps[app]
                return (
                  <Card key={app}>
                    <CardHeader>
                      <IconTile icon={meta.icon} />
                      <CardTitle>{meta.name}</CardTitle>
                      <CardDescription className="leading-relaxed">{meta.role}</CardDescription>
                    </CardHeader>
                    <CardFooter className="flex flex-wrap items-center gap-2">
                      <Badge variant={simulate || state?.connected ? "default" : "outline"}>{appState(app)}</Badge>
                      {!simulate && connections?.composio && state?.via !== "composio" ? (
                        <Button size="sm" variant="outline" disabled={!/^[\w.@+-]{1,200}$/.test(userId) || busy !== null} onClick={() => void connect(app)}>
                          {busy === `connect-${app}` ? <Spinner data-icon="inline-start" /> : null}
                          Connect
                        </Button>
                      ) : null}
                    </CardFooter>
                  </Card>
                )
              })}
            </div>
            <Alert>
              <AlertTitle>How they work together</AlertTitle>
              <AlertDescription>Gmail draft → Calendar reminder with the email link → HubSpot deal with both links → one Slack message with all three.</AlertDescription>
            </Alert>
          </Screen>
        )

      case "job":
        return (
          <Screen
            eyebrow="Step 2 · The job"
            title={job ? `${job.role} at ${job.company}` : "Loading the job…"}
            description="A fixed job post from the test set and the sample resume, so this run is repeatable."
          >
            <div className="grid gap-4 lg:grid-cols-2">
              {[
                { title: "The job post", text: job?.jd_text },
                { title: "The resume", text: resume },
              ].map((doc) => (
                <Card key={doc.title}>
                  <CardHeader>
                    <CardTitle>{doc.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-72 rounded-lg border">
                      <p className="p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap">{doc.text || "Loading…"}</p>
                    </ScrollArea>
                  </CardContent>
                </Card>
              ))}
            </div>
            {runButton("Run the agent", "fit", Play, startFit)}
          </Screen>
        )

      case "agents":
        return (
          <Screen
            eyebrow="Step 3 · Three agents"
            title="Researcher, Tailor, Executor."
            description="The Researcher reads the job, the Tailor rewrites from real lines, and the Executor checks every receipt before choosing which apps to act in."
          >
            <PipelineCard state={pipeline.state} />
            {fit && busy !== "fit" ? (
              <Alert>
                <AlertTitle className="flex items-center gap-2">
                  <Badge variant={fitOutcome?.variant}>{fitOutcome?.label}</Badge>
                  {fit.role} at {fit.company}
                </AlertTitle>
                <AlertDescription>
                  Keyword overlap {pct(fit.guardrail.score)} · Executor {fit.executor_mode} · {fit.used_live_llm ? "live LLM" : "rule-based fallback"}
                </AlertDescription>
              </Alert>
            ) : busy !== "fit" ? (
              runButton("Run the agent", "fit", Play)
            ) : null}
          </Screen>
        )

      case "receipts":
        return (
          <Screen
            eyebrow="Step 4 · Receipts"
            title="Every line points to where it came from."
            description="The Executor matches each tailored line to the resume in code. One line it can't match blocks every app."
          >
            {fit ? (
              <Card>
                <CardContent>
                  <Receipts result={fit} />
                </CardContent>
              </Card>
            ) : (
              needsFitNotice
            )}
          </Screen>
        )

      case "apps":
        return (
          <Screen
            eyebrow="Step 5 · Apps hand off"
            title="One application, four apps, every link passed along."
            description="Gmail's link goes into the Calendar reminder, both go onto the HubSpot deal, and Slack gets all three."
          >
            {fit ? (
              <div className="grid gap-4 lg:grid-cols-4">
                {APPS.map((app, i) => {
                  const action = fit.actions[app]
                  const meta = APP_META[app]
                  const link = safeUrl(action?.link)
                  return (
                    <Card key={app}>
                      <CardHeader>
                        <div className="flex items-center justify-between gap-2">
                          <IconTile icon={meta.icon} />
                          <Badge variant="outline">{i + 1}</Badge>
                        </div>
                        <CardTitle>{meta.name}</CardTitle>
                        <CardDescription className="leading-relaxed">{action?.detail ?? "Not run for this application."}</CardDescription>
                      </CardHeader>
                      <CardFooter className="flex flex-wrap items-center gap-2">
                        <Badge variant={statusVariant(action?.status)}>{action?.status ?? "skipped"}</Badge>
                        {link ? (
                          <Button size="sm" variant="outline" nativeButton={false} render={<a href={link} target="_blank" rel="noopener noreferrer" />}>
                            Open
                          </Button>
                        ) : null}
                      </CardFooter>
                    </Card>
                  )
                })}
              </div>
            ) : (
              needsFitNotice
            )}
          </Screen>
        )

      case "reply":
        return (
          <Screen eyebrow="Step 6 · They reply" title="A reply closes the loop across the apps." description="When the employer answers, the agent updates the CRM, cancels the follow-up it booked, and tells you in Slack.">
            {fit ? runButton("Simulate the employer's reply", "reply", MailCheck) : needsFitNotice}
            {steps.reply ? (
              <StepResultCards results={steps.reply} labels={{ crm: "HubSpot deal → Replied", calendar: "Follow-up cancelled", slack: "Slack pinged" }} />
            ) : null}
          </Screen>
        )

      case "bait":
        return (
          <Screen
            eyebrow="Step 7 · Honesty gate"
            title="A job that baits the agent into lying."
            description="It demands Terraform, GCP, Go and a Kubernetes certification the resume doesn't have. Watch what happens."
          >
            {runButton("Run the bait job", "bait", ShieldAlert)}
            {runs.bait ? (
              <div className="grid items-start gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
                <Card>
                  <CardHeader>
                    <CardDescription>Outcome</CardDescription>
                    <CardTitle>
                      <Badge variant={OUTCOMES[runs.bait.outcome]?.variant}>{OUTCOMES[runs.bait.outcome]?.label}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2 text-sm text-muted-foreground">
                    <span>Keyword overlap {pct(runs.bait.guardrail.score)}</span>
                    <span>
                      Apps acted in:{" "}
                      <span className="font-semibold text-kpi-yellow">
                        {Object.keys(runs.bait.actions).filter((k) => k !== "slack").length || "none"}
                      </span>
                    </span>
                    <span>Slack was told why.</span>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>What the job wants that the resume doesn't show</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Gaps gaps={runs.bait.gap_report} />
                  </CardContent>
                </Card>
              </div>
            ) : null}
          </Screen>
        )

      case "chaos":
        return (
          <Screen
            eyebrow="Step 8 · Chaos test"
            title="Gmail goes down in the middle of a run."
            description="The chaos panel breaks Gmail on purpose. The agent retries, reports a clear reason, finishes the other apps, and doesn't crash."
          >
            {runButton("Break Gmail and run", "chaos", FlaskConical)}
            {busy === "chaos" || runs.chaos ? <PipelineCard state={pipeline.state} /> : null}
            {runs.chaos && busy !== "chaos" ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {APPS.map((app) => {
                  const action = runs.chaos?.actions[app]
                  return (
                    <Card key={app}>
                      <CardHeader>
                        <CardTitle>{APP_META[app].name}</CardTitle>
                        <CardDescription className="leading-relaxed">{action?.detail ?? "Not run."}</CardDescription>
                      </CardHeader>
                      <CardFooter>
                        <Badge variant={statusVariant(action?.status)}>{action?.status ?? "skipped"}</Badge>
                      </CardFooter>
                    </Card>
                  )
                })}
              </div>
            ) : null}
          </Screen>
        )

      case "undo":
        return (
          <Screen eyebrow="Step 9 · Undo" title="Changed your mind? One click reverses it." description="Undo deletes the draft and reminder, closes the CRM deal, and tells Slack, across every app the application touched.">
            {fit ? runButton("Undo the application", "undo", Undo2) : needsFitNotice}
            {steps.undo ? (
              <StepResultCards
                results={steps.undo}
                labels={{ gmail: "Gmail draft deleted", calendar: "Calendar reminder", crm: "HubSpot deal closed", slack: "Slack notified" }}
              />
            ) : null}
          </Screen>
        )

      case "proof":
        return (
          <Screen eyebrow="How we know it works" title="Tested on purpose, including when things break." description="Ten job descriptions scored on four checks, then the same suite with Gmail down and the model rate-limited.">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi tone="emerald" label="Test suite" value={summary.normal ? `${summary.normal.passed}/${summary.normal.total}` : "—"} hint="Normal run" />
              <Kpi tone="emerald" label="Under failures" value={summary.faults ? `${summary.faults.passed}/${summary.faults.total}` : "—"} hint="Gmail down + LLM rate-limited" />
              <Kpi
                tone="emerald"
                label="Apps acted in"
                value={fit ? `${Object.values(fit.actions).filter((a) => a.status === "ok" || a.status === "mocked").length}/4` : "—"}
                hint="In this demo's application"
              />
              <Kpi tone="yellow" label="Stopped by a gate" value={String(history.filter((r) => r.outcome === "flagged" || r.outcome === "duplicate").length)} hint="Nothing sent, Slack told why" />
            </div>
            <div className="flex flex-wrap gap-3">
              <Button size="lg" nativeButton={false} render={<a href="/app" />}>
                <LayoutDashboard data-icon="inline-start" />
                Open the dashboard
              </Button>
              <Button size="lg" variant="outline" nativeButton={false} render={<a href="https://github.com/charansaiponnada/honest-apply" target="_blank" rel="noopener noreferrer" />}>
                Source on GitHub
              </Button>
            </div>
          </Screen>
        )
    }
  }

  return (
    <div className={`${theme === "dark" ? "demo-theme-dark" : "demo-theme-light"} flex min-h-svh flex-col bg-background text-foreground`}>
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck aria-hidden="true" />
            </span>
            Honest Apply
          </a>
          <Badge variant="secondary">
            {index + 1} / {SCREENS.length} · {SCREEN_LABELS[screen]}
          </Badge>
          <div className="ml-auto flex items-center gap-3">
            <Field orientation="horizontal" className="w-auto">
              <Switch id="demo-live" checked={!simulate} onCheckedChange={(checked: boolean) => setSimulate(!checked)} />
              <FieldLabel htmlFor="demo-live" className="whitespace-nowrap">
                {simulate ? "Simulated" : "Live apps"}
              </FieldLabel>
            </Field>
            {APPS.map((app) => (
              <Badge key={app} variant={simulate || connections?.apps[app].connected ? "default" : "outline"} className="hidden lg:inline-flex">
                {APP_LABELS[app]}
              </Badge>
            ))}
            <Button variant="outline" size="icon" aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun /> : <Moon />}
            </Button>
          </div>
        </div>
      </header>

      <main className="flex flex-1 items-start px-4 py-10 sm:py-14">
        <div key={screen} className="w-full">
          {renderScreen()}
        </div>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <Button variant="outline" disabled={index === 0} onClick={() => goTo(SCREENS[index - 1])}>
            <ArrowLeft data-icon="inline-start" />
            Back
          </Button>
          <nav className="mx-auto flex flex-wrap justify-center gap-2" aria-label="Demo steps">
            {SCREENS.map((id, i) => (
              <button
                key={id}
                type="button"
                aria-label={`Go to ${SCREEN_LABELS[id]}`}
                aria-current={id === screen ? "step" : undefined}
                onClick={() => goTo(id)}
                className={`h-2.5 rounded-full transition-all duration-200 ${id === screen ? "w-8 bg-primary" : i < index ? "w-2.5 bg-kpi-emerald/60" : "w-2.5 bg-border"}`}
              />
            ))}
          </nav>
          <Button disabled={index === SCREENS.length - 1} onClick={() => goTo(SCREENS[index + 1])}>
            Next
            <ArrowRight data-icon="inline-end" />
          </Button>
        </div>
      </footer>
    </div>
  )
}
