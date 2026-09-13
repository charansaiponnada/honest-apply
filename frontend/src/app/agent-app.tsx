import type { LucideIcon } from "lucide-react"
import { Bot, BriefcaseBusiness, House, LayoutDashboard, ListChecks, Plug, ShieldCheck, Upload } from "lucide-react"
import type { ReactNode } from "react"
import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { api, store, streamEvents } from "@/app/api"
import { LiveJobsCard, RecommendationsCard } from "@/app/jobs"
import type { Section } from "@/app/overview"
import { Overview } from "@/app/overview"
import { PipelineCard, usePipeline } from "@/app/pipeline"
import { Reliability } from "@/app/reliability"
import { ResultView } from "@/app/result-view"
import type { Profile, RunDetails } from "@/app/sidebar"
import { ChaosCard, RunDetailsCard, YourAppsCard } from "@/app/sidebar"
import { Tracker } from "@/app/tracker"
import type { AppKey, Connections, Job, PipelineEvent, RunResult, Status } from "@/app/types"
import { APP_LABELS } from "@/app/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Separator } from "@/components/ui/separator"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Textarea } from "@/components/ui/textarea"

const SECTIONS: { id: Section; label: string; description: string; icon: LucideIcon }[] = [
  { id: "overview", label: "Overview", description: "Your applications, reliability and next steps", icon: LayoutDashboard },
  { id: "run", label: "Run agent", description: "Tailor with receipts, then act across your apps", icon: Bot },
  { id: "jobs", label: "Find jobs", description: "Live listings ranked by skills you can prove", icon: BriefcaseBusiness },
  { id: "tracker", label: "Tracker", description: "Every application, reply and undo", icon: ListChecks },
  { id: "reliability", label: "Reliability", description: "The test suite, normally and with failures injected", icon: ShieldCheck },
  { id: "apps", label: "Apps & profile", description: "Connect Gmail, Calendar, HubSpot and Slack; add GitHub", icon: Plug },
]

const APPS: AppKey[] = ["gmail", "calendar", "crm", "slack"]

function initialSection(): Section {
  const hash = window.location.hash.slice(1)
  return SECTIONS.some((s) => s.id === hash) ? (hash as Section) : "overview"
}

/** Sections stay mounted (keeping their state) and fade in when shown. */
function Panel({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <div hidden={!active} className="animate-in duration-200 fade-in slide-in-from-bottom-1 motion-reduce:animate-none">
      {children}
    </div>
  )
}

export function AgentApp() {
  const [section, setSection] = useState<Section>(initialSection)
  const [status, setStatus] = useState<Status | null>(null)
  const [connections, setConnections] = useState<Connections | null>(null)
  const [profile, setProfile] = useState<Profile>(() => ({
    userId: store.get("userId"),
    github: store.get("github"),
    slackChannel: store.get("slackChannel"),
  }))
  const [resume, setResume] = useState("")
  const [jd, setJd] = useState("")
  const [jdSource, setJdSource] = useState("pasted text")
  const [details, setDetails] = useState<RunDetails>({ company: "", role: "", recipient: "", allowSend: false })
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<RunResult | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const results = useRef<Record<string, RunResult>>({})
  const resultRef = useRef<HTMLDivElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const pipeline = usePipeline()
  const current = SECTIONS.find((s) => s.id === section) ?? SECTIONS[0]

  useEffect(() => {
    document.title = "Dashboard · Honest Apply"
    Promise.all([api<Status>("/api/status"), api<{ resume: string }>("/api/defaults")])
      .then(([s, defaults]) => {
        setStatus(s)
        setResume((existing) => existing || defaults.resume)
      })
      .catch((err: Error) => setError(`Could not reach the server: ${err.message}`))
    const connected = new URLSearchParams(window.location.search).get("connected")
    if (connected) {
      toast.success(`${APP_LABELS[connected as AppKey] ?? "App"} connected.`)
      window.history.replaceState(null, "", "/app#apps")
      setSection("apps")
    }
  }, [])

  const navigate = useCallback((next: Section) => {
    setSection(next)
    window.history.replaceState(null, "", `#${next}`)
    if (next === "tracker" || next === "overview") setRefreshKey((k) => k + 1)
    window.scrollTo({ top: 0 })
  }, [])

  const onConnections = useCallback((c: Connections) => setConnections(c), [])

  const showResult = useCallback(
    (r: RunResult) => {
      results.current[r.run_id] = r
      setResult(r)
      navigate("run")
      requestAnimationFrame(() =>
        resultRef.current?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }),
      )
    },
    [navigate],
  )

  const handleEvent = useCallback(
    (event: PipelineEvent) => {
      pipeline.handle(event)
      if (event.type === "result") showResult(event.result)
      if (event.type === "error") setError(event.detail)
    },
    [pipeline, showResult],
  )

  const useJob = useCallback(
    (job: Job) => {
      setJd(job.description || job.title)
      setDetails((d) => ({ ...d, company: job.company_name, role: job.title }))
      setJdSource(job.url || job.source || "job board")
      navigate("run")
      toast.success(`Loaded ${job.title} at ${job.company_name}`)
    },
    [navigate],
  )

  async function runAgent() {
    if (resume.trim().length < 20 || jd.trim().length < 20) {
      setError("Add a resume and a job description (at least 20 characters each).")
      return
    }
    pipeline.reset()
    setError(null)
    setResult(null)
    setRunning(true)
    try {
      await streamEvents(
        "/api/run",
        {
          resume_text: resume,
          jd_text: jd,
          company: details.company,
          role: details.role,
          recipient: details.recipient,
          allow_send: details.allowSend,
          jd_source: jdSource,
          user_id: profile.userId,
          slack_channel: profile.slackChannel,
          github_username: profile.github,
        },
        handleEvent,
      )
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setRunning(false)
      setRefreshKey((k) => k + 1)
    }
  }

  const undo = useCallback(async (runId: string) => {
    try {
      const res = await api<{ already_undone: boolean; results: Record<string, { status: string }> }>(`/api/undo/${encodeURIComponent(runId)}`, {
        method: "POST",
      })
      const summary = Object.entries(res.results)
        .map(([app, r]) => `${APP_LABELS[app as AppKey] ?? app}: ${r.status}`)
        .join(" · ")
      toast.success(res.already_undone ? "Already undone." : `Undone. ${summary}`)
      setRefreshKey((k) => k + 1)
      return true
    } catch (err) {
      toast.error((err as Error).message)
      return false
    }
  }, [])

  async function uploadResume(file: File) {
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Resume file is over 5 MB.")
      return
    }
    try {
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "")
        reader.onerror = () => reject(new Error("Could not read that file."))
        reader.readAsDataURL(file)
      })
      const res = await api<{ text: string }>("/api/resume/parse", { body: { filename: file.name, data_base64: data } })
      setResume(res.text)
      toast.success(`Loaded ${file.name}`)
    } catch (err) {
      toast.error((err as Error).message)
    }
  }

  const gmailConnected = connections?.apps.gmail.connected ?? status?.google ?? false
  const statusItems: [string, boolean | undefined][] = [
    ["LLM", status?.llm],
    ...APPS.map((app): [string, boolean | undefined] => [APP_LABELS[app], connections?.apps[app].connected]),
  ]

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon" variant="inset">
        <SidebarHeader>
          <a href="/" className="flex items-center gap-2 rounded-lg p-1.5 font-semibold">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck aria-hidden="true" />
            </span>
            <span className="truncate group-data-[collapsible=icon]:hidden">Honest Apply</span>
          </a>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Agent</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {SECTIONS.map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton isActive={section === item.id} tooltip={item.label} onClick={() => navigate(item.id)}>
                      <item.icon />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <SidebarGroup className="group-data-[collapsible=icon]:hidden">
            <SidebarGroupLabel>Status</SidebarGroupLabel>
            <div className="flex flex-wrap gap-1.5 px-2">
              {statusItems.map(([label, live]) => (
                <Badge key={label} variant={live ? "default" : "outline"} title={label === "LLM" ? status?.model : undefined}>
                  {label}
                </Badge>
              ))}
            </div>
          </SidebarGroup>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton tooltip="Home page" render={<a href="/" />}>
                <House />
                <span>Home page</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset>
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-4 backdrop-blur">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mx-1 h-4" />
          <div className="flex min-w-0 flex-col">
            <h1 className="truncate text-sm font-semibold">{current.label}</h1>
            <p className="hidden truncate text-xs text-muted-foreground sm:block">{current.description}</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {status?.faults.length ? <Badge variant="destructive">Chaos: {status.faults.join(", ")}</Badge> : null}
            {section !== "run" ? (
              <Button size="sm" onClick={() => navigate("run")}>
                <Bot data-icon="inline-start" />
                Run agent
              </Button>
            ) : null}
          </div>
        </header>

        <div className="mx-auto flex w-full max-w-7xl flex-col p-4 md:p-6">
          <Panel active={section === "overview"}>
            <Overview status={status} connections={connections} refreshKey={refreshKey} onNavigate={navigate} />
          </Panel>

          <Panel active={section === "run"}>
            <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="flex min-w-0 flex-col gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Resume and job</CardTitle>
                    <CardDescription>Upload a PDF or paste text. The agent only uses what's here and in your GitHub.</CardDescription>
                    <CardAction>
                      <input
                        ref={fileInput}
                        type="file"
                        accept=".pdf,.txt"
                        className="sr-only"
                        aria-label="Upload resume"
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          e.target.value = ""
                          if (file) void uploadResume(file)
                        }}
                      />
                      <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()}>
                        <Upload data-icon="inline-start" />
                        Upload PDF
                      </Button>
                    </CardAction>
                  </CardHeader>
                  <CardContent>
                    <FieldGroup className="grid gap-4 md:grid-cols-2">
                      <Field>
                        <FieldLabel htmlFor="resume">Your resume</FieldLabel>
                        <Textarea id="resume" className="min-h-72 font-mono text-xs" value={resume} onChange={(e) => setResume(e.target.value)} />
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="jd">Job description</FieldLabel>
                        <Textarea
                          id="jd"
                          className="min-h-72 font-mono text-xs"
                          placeholder="Paste a job description, or pick one in Find jobs."
                          value={jd}
                          onChange={(e) => {
                            setJd(e.target.value)
                            setJdSource("pasted text")
                          }}
                        />
                      </Field>
                    </FieldGroup>
                  </CardContent>
                </Card>
                <PipelineCard state={pipeline.state} />
                {error ? (
                  <Alert variant="destructive">
                    <AlertTitle>Something went wrong</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                ) : null}
                <div ref={resultRef} className="scroll-mt-20">
                  {result ? <ResultView key={result.run_id} result={result} onUndo={undo} /> : null}
                </div>
              </div>
              <div className="flex flex-col gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Connected apps</CardTitle>
                    <CardDescription>Actions run on these accounts.</CardDescription>
                    <CardAction>
                      <Button variant="ghost" size="sm" onClick={() => navigate("apps")}>
                        Manage
                      </Button>
                    </CardAction>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-2">
                    {APPS.map((app) => (
                      <Badge key={app} variant={connections?.apps[app].connected ? "default" : "outline"}>
                        {APP_LABELS[app]}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>
                <RunDetailsCard details={details} onChange={setDetails} status={status} gmailConnected={gmailConnected} running={running} onRun={() => void runAgent()} />
                <ChaosCard status={status} onFaults={(faults) => setStatus((s) => (s ? { ...s, faults } : s))} />
              </div>
            </div>
          </Panel>

          <Panel active={section === "jobs"}>
            <div className="flex flex-col gap-6">
              <RecommendationsCard
                resume={resume}
                github={profile.github}
                userId={profile.userId}
                slackChannel={profile.slackChannel}
                onUseJob={useJob}
                onEvent={pipeline.handle}
                onResult={(r) => {
                  results.current[r.run_id] = r
                  setRefreshKey((k) => k + 1)
                }}
                onShowResult={(runId) => {
                  const r = results.current[runId]
                  if (r) showResult(r)
                }}
              />
              <LiveJobsCard onUseJob={useJob} />
            </div>
          </Panel>

          <Panel active={section === "tracker"}>
            <Tracker googleLive={status?.google ?? false} refreshKey={refreshKey} onUndo={undo} />
          </Panel>

          <Panel active={section === "reliability"}>
            <div className="flex flex-col gap-6">
              <Reliability />
              <ChaosCard status={status} onFaults={(faults) => setStatus((s) => (s ? { ...s, faults } : s))} />
            </div>
          </Panel>

          <Panel active={section === "apps"}>
            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,26rem)_1fr]">
              <YourAppsCard profile={profile} onProfileChange={setProfile} onConnections={onConnections} />
              <Card>
                <CardHeader>
                  <CardTitle>How connections work</CardTitle>
                  <CardDescription>Each app is used in this order for every run.</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4 text-sm leading-relaxed">
                  <p>
                    <span className="font-medium">1. Your account via Composio.</span> Click Connect and sign in; Composio stores and
                    refreshes the tokens, and the agent acts on your own Gmail, Calendar, HubSpot and Slack.
                  </p>
                  <p>
                    <span className="font-medium">2. Server keys.</span> If the server has its own credentials in <code>.env</code>, apps
                    you haven't connected use those.
                  </p>
                  <p>
                    <span className="font-medium">3. Mock mode.</span> With neither, actions are written to local files so the whole
                    pipeline still runs and is clearly labeled.
                  </p>
                  <Separator />
                  <p className="text-muted-foreground">
                    Your GitHub username lets the agent add skills your public repos prove, with the repo named as the receipt. Undo
                    and reply tracking always use the same account the run used.
                  </p>
                </CardContent>
              </Card>
            </div>
          </Panel>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
