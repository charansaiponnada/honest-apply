import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { api, store, streamEvents } from "@/app/api"
import { LiveJobsCard, RecommendationsCard } from "@/app/jobs"
import { PipelineCard, usePipeline } from "@/app/pipeline"
import { Reliability } from "@/app/reliability"
import { ResultView } from "@/app/result-view"
import type { Profile, RunDetails } from "@/app/sidebar"
import { ChaosCard, RunDetailsCard, YourAppsCard } from "@/app/sidebar"
import { Tracker } from "@/app/tracker"
import type { Connections, Job, PipelineEvent, RunResult, Status } from "@/app/types"
import { APP_LABELS } from "@/app/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

const TABS = ["run", "tracker", "reliability"] as const
type Tab = (typeof TABS)[number]

function initialTab(): Tab {
  const hash = window.location.hash.slice(1)
  return (TABS as readonly string[]).includes(hash) ? (hash as Tab) : "run"
}

export function AgentApp() {
  const [tab, setTab] = useState<Tab>(initialTab)
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
  const [trackerKey, setTrackerKey] = useState(0)
  const results = useRef<Record<string, RunResult>>({})
  const resultRef = useRef<HTMLDivElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const pipeline = usePipeline()

  useEffect(() => {
    Promise.all([api<Status>("/api/status"), api<{ resume: string }>("/api/defaults")])
      .then(([s, defaults]) => {
        setStatus(s)
        setResume((current) => current || defaults.resume)
      })
      .catch((err: Error) => setError(`Could not reach the server: ${err.message}`))
    const connected = new URLSearchParams(window.location.search).get("connected")
    if (connected) {
      toast.success(`${APP_LABELS[connected as keyof typeof APP_LABELS] ?? "App"} connected.`)
      window.history.replaceState(null, "", "/app")
    }
  }, [])

  useEffect(() => {
    window.history.replaceState(null, "", `#${tab}`)
    if (tab === "tracker") setTrackerKey((k) => k + 1)
  }, [tab])

  const onConnections = useCallback((c: Connections) => setConnections(c), [])

  const showResult = useCallback((r: RunResult) => {
    results.current[r.run_id] = r
    setResult(r)
    requestAnimationFrame(() =>
      resultRef.current?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }),
    )
  }, [])

  const handleEvent = useCallback(
    (event: PipelineEvent) => {
      pipeline.handle(event)
      if (event.type === "result") showResult(event.result)
      if (event.type === "error") setError(event.detail)
    },
    [pipeline, showResult],
  )

  const useJob = useCallback((job: Job) => {
    setJd(job.description || job.title)
    setDetails((d) => ({ ...d, company: job.company_name, role: job.title }))
    setJdSource(job.url || job.source || "job board")
    toast.success(`Loaded ${job.title} at ${job.company_name}`)
  }, [])

  async function runAgent() {
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
    }
  }

  const undo = useCallback(async (runId: string) => {
    try {
      const res = await api<{ already_undone: boolean; results: Record<string, { status: string }> }>(`/api/undo/${encodeURIComponent(runId)}`, {
        method: "POST",
      })
      const summary = Object.entries(res.results)
        .map(([app, r]) => `${APP_LABELS[app as keyof typeof APP_LABELS] ?? app}: ${r.status}`)
        .join(" · ")
      toast.success(res.already_undone ? "Already undone." : `Undone. ${summary}`)
      setTrackerKey((k) => k + 1)
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
  const statusBadges: [string, boolean | undefined][] = [
    ["LLM", status?.llm],
    ["Gmail", connections?.apps.gmail.connected ?? status?.google],
    ["HubSpot", connections?.apps.crm.connected ?? status?.crm],
    ["Slack", connections?.apps.slack.connected ?? status?.slack],
  ]

  return (
    <div className="min-h-svh bg-background">
      {status?.faults.length ? (
        <div className="border-b bg-destructive/10 px-4 py-2 text-center text-sm text-destructive">
          Chaos panel active: {status.faults.join(", ")}
        </div>
      ) : null}
      <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
        <header className="sticky top-0 z-10 border-b bg-background/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-4 py-3">
            <a href="/" className="flex items-center gap-2 font-semibold">
              <span className="size-6 rounded-md bg-primary" aria-hidden="true" />
              Honest Apply
            </a>
            <TabsList>
              <TabsTrigger value="run">Run agent</TabsTrigger>
              <TabsTrigger value="tracker">Tracker</TabsTrigger>
              <TabsTrigger value="reliability">Reliability</TabsTrigger>
            </TabsList>
            <div className="ml-auto flex flex-wrap gap-2" aria-label="Integration status">
              {statusBadges.map(([label, live]) => (
                <Badge key={label} variant={live ? "default" : "outline"} title={label === "LLM" ? status?.model : undefined}>
                  {label} · {live ? "live" : "mock"}
                </Badge>
              ))}
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-6">
          <TabsContent value="run" className="flex flex-col gap-4">
            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="flex min-w-0 flex-col gap-4">
                <RecommendationsCard
                  resume={resume}
                  github={profile.github}
                  userId={profile.userId}
                  slackChannel={profile.slackChannel}
                  onUseJob={useJob}
                  onEvent={pipeline.handle}
                  onResult={(r) => (results.current[r.run_id] = r)}
                  onShowResult={(runId) => {
                    const r = results.current[runId]
                    if (r) showResult(r)
                  }}
                />
                <LiveJobsCard onUseJob={useJob} />
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
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          e.target.value = ""
                          if (file) void uploadResume(file)
                        }}
                      />
                      <Button variant="outline" size="sm" onClick={() => fileInput.current?.click()}>
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
                          placeholder="Paste a job description, or pick a job above."
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
              </div>
              <aside className="flex flex-col gap-4">
                <YourAppsCard profile={profile} onProfileChange={setProfile} onConnections={onConnections} />
                <RunDetailsCard
                  details={details}
                  onChange={setDetails}
                  status={status}
                  gmailConnected={gmailConnected}
                  running={running}
                  onRun={() => {
                    if (resume.trim().length < 20 || jd.trim().length < 20) {
                      setError("Add a resume and a job description (at least 20 characters each).")
                      return
                    }
                    void runAgent()
                  }}
                />
                <ChaosCard status={status} onFaults={(faults) => setStatus((s) => (s ? { ...s, faults } : s))} />
              </aside>
            </div>
            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Something went wrong</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            <div ref={resultRef}>{result ? <ResultView key={result.run_id} result={result} onUndo={undo} /> : null}</div>
          </TabsContent>

          <TabsContent value="tracker">
            <Tracker googleLive={status?.google ?? false} refreshKey={trackerKey} onUndo={undo} />
          </TabsContent>

          <TabsContent value="reliability">
            <Reliability />
          </TabsContent>
        </main>
      </Tabs>
    </div>
  )
}
