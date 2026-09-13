import { motion } from "framer-motion"
import type { LucideIcon } from "lucide-react"
import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Building2,
  CalendarClock,
  Check,
  CircleAlert,
  CircleCheck,
  CopyX,
  FileSearch,
  FlaskConical,
  FolderGit2,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  Mail,
  MessageSquare,
  PenLine,
  Play,
  Route,
  ShieldCheck,
  Undo2,
  UserRoundCheck,
  Users,
  X,
} from "lucide-react"
import type { ReactNode } from "react"
import { useEffect, useRef, useState } from "react"

import { api, pct, streamEvents } from "@/app/api"
import type { AppKey, EvalSummary, PipelineEvent, RunResult } from "@/app/types"
import { APP_LABELS, OUTCOMES } from "@/app/types"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const REPO = "https://github.com/charansaiponnada/honest-apply"

function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.3, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  )
}

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="flex max-w-3xl flex-col gap-3">
      <span className="text-sm font-semibold tracking-wide text-kpi-emerald uppercase">{eyebrow}</span>
      <h2 className="text-3xl font-bold tracking-tight text-balance sm:text-5xl">{title}</h2>
      <p className="text-lg leading-relaxed text-pretty text-muted-foreground">{description}</p>
    </div>
  )
}

function IconTile({ icon: Icon, tone = "emerald" }: { icon: LucideIcon; tone?: "emerald" | "yellow" }) {
  return (
    <span className={`flex size-11 shrink-0 items-center justify-center rounded-lg bg-secondary ${tone === "emerald" ? "text-kpi-emerald" : "text-kpi-yellow"}`}>
      <Icon aria-hidden="true" />
    </span>
  )
}

const LinkButton = ({ href, children, variant = "default", size = "lg" }: { href: string; children: ReactNode; variant?: "default" | "outline" | "ghost" | "secondary"; size?: "lg" | "default" | "sm" }) => (
  <Button variant={variant} size={size} nativeButton={false} render={<a href={href} />}>
    {children}
  </Button>
)

// ---------------------------------------------------------------------------- live agent console

type Tone = "run" | "ok" | "warn" | "error" | "info"
interface ConsoleLine {
  id: number
  icon: LucideIcon
  text: string
  tone: Tone
}

const APP_ICONS: Record<AppKey, LucideIcon> = { gmail: Mail, calendar: CalendarClock, crm: Building2, slack: MessageSquare }

const PREVIEW: { icon: LucideIcon; text: string }[] = [
  { icon: FileSearch, text: "Researcher reads the job post and extracts requirements" },
  { icon: PenLine, text: "Tailor rewrites the resume from real lines, citing each source" },
  { icon: ShieldCheck, text: "Executor checks receipts, overlap, seniority and duplicates" },
  { icon: Route, text: "Executor plans which apps to call with tool calling" },
  { icon: Mail, text: "Gmail → Calendar → HubSpot → Slack, each passing its link on" },
]

const TONE_CLASS: Record<Tone, string> = {
  run: "text-foreground",
  ok: "text-kpi-emerald",
  warn: "text-kpi-yellow",
  error: "text-destructive",
  info: "text-muted-foreground",
}

let lineId = 0

function AgentConsole() {
  const [lines, setLines] = useState<ConsoleLine[]>([])
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<RunResult | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" })
  }, [lines])

  const push = (tone: Tone, icon: LucideIcon, text: string) => setLines((prev) => [...prev, { id: ++lineId, tone, icon, text }])

  function onEvent(event: PipelineEvent) {
    switch (event.type) {
      case "step": {
        const messages: Record<string, [Tone, LucideIcon, string]> = {
          "researcher:running": ["run", FileSearch, "Researcher is reading the job post…"],
          "researcher:done": ["ok", FileSearch, "Requirements extracted: skills, seniority, must-haves"],
          "tailor:running": ["run", PenLine, "Tailor is rewriting from real resume lines…"],
          "tailor:done": ["ok", PenLine, "Tailored resume ready, each line cites its source"],
          "executor:reviewing": ["run", ShieldCheck, "Executor is checking receipts, overlap, seniority and duplicates…"],
          "executor:acting": ["run", Route, "Deciding which apps to act in…"],
        }
        const message = messages[`${event.step}:${event.status}`]
        if (message) push(...message)
        else if (event.step === "executor") {
          const outcome = OUTCOMES[event.status as keyof typeof OUTCOMES]
          push(event.status === "drafted" || event.status === "sent" ? "ok" : "warn", CircleCheck, `Outcome: ${outcome?.label ?? event.status}`)
        }
        break
      }
      case "tool":
        if (event.status !== "running") {
          push(event.status === "error" ? "error" : "ok", APP_ICONS[event.app] ?? Bot, `${APP_LABELS[event.app]}: ${event.detail ?? event.status}`)
        }
        break
      case "github":
        if (event.verified.length) push("ok", FolderGit2, `GitHub proves: ${event.verified.join(", ")}`)
        break
      case "fault":
        push("warn", FlaskConical, `Chaos: ${event.names.join(", ")} switched off`)
        break
      case "result":
        setResult(event.result)
        break
      case "error":
        push("error", CircleAlert, event.detail)
        break
    }
  }

  async function start() {
    setRunning(true)
    setLines([])
    setResult(null)
    try {
      const [defaults, scenarios] = await Promise.all([
        api<{ resume: string }>("/api/defaults"),
        api<Record<string, { company: string; role: string; jd_text: string }>>("/api/demo/scenarios"),
      ])
      const job = scenarios.good_fit
      push("info", UserRoundCheck, `Goal: apply to ${job.role} at ${job.company} without inventing anything`)
      await streamEvents(
        "/api/run",
        {
          resume_text: defaults.resume,
          jd_text: job.jd_text,
          company: job.company,
          role: job.role,
          jd_source: "landing: live run",
          allow_duplicate: true,
          simulate: true,
        },
        onEvent,
      )
    } catch (err) {
      push("error", CircleAlert, `Couldn't reach the agent: ${(err as Error).message}. Start the server with uvicorn main:app.`)
    } finally {
      setRunning(false)
    }
  }

  const receipts = result?.executor_verdict.receipts ?? []
  const actedIn = result ? Object.entries(result.actions).filter(([, a]) => a.status === "ok" || a.status === "mocked").length : 0

  return (
    <Card className="border-kpi-emerald/30 shadow-2xl shadow-kpi-emerald/10">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <CardTitle className="flex items-center gap-2">
              <span className={`size-2.5 rounded-full ${running ? "animate-pulse bg-kpi-yellow motion-reduce:animate-none" : result ? "bg-kpi-emerald" : "bg-muted-foreground"}`} aria-hidden="true" />
              Agent console
            </CardTitle>
            <CardDescription>A real run, streamed live. Simulated apps, so no accounts are touched.</CardDescription>
          </div>
          <Button onClick={() => void start()} disabled={running}>
            {running ? <Spinner data-icon="inline-start" /> : <Play data-icon="inline-start" />}
            {running ? "Planning…" : result ? "Run again" : "Watch it plan"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-80 rounded-lg border bg-muted/40">
          <ol className="flex flex-col gap-2 p-4 font-mono text-sm" aria-live="polite">
            {lines.length === 0
              ? PREVIEW.map((step, i) => (
                  <li key={step.text} className="flex items-start gap-3 text-muted-foreground">
                    <span className="w-5 shrink-0 text-right tabular-nums">{i + 1}</span>
                    <step.icon className="mt-0.5 shrink-0" aria-hidden="true" />
                    <span>{step.text}</span>
                  </li>
                ))
              : lines.map((line) => (
                  <motion.li
                    key={line.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2 }}
                    className={`flex items-start gap-3 ${TONE_CLASS[line.tone]}`}
                  >
                    <line.icon className="mt-0.5 shrink-0" aria-hidden="true" />
                    <span className="leading-relaxed">{line.text}</span>
                  </motion.li>
                ))}
            <div ref={endRef} />
          </ol>
        </ScrollArea>
      </CardContent>
      {result ? (
        <CardFooter className="flex flex-col items-stretch gap-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Receipts", value: `${receipts.filter((r) => r.supported).length}/${receipts.length}` },
              { label: "Overlap", value: pct(result.guardrail.score) },
              { label: "Apps acted in", value: `${actedIn}/4` },
            ].map((stat) => (
              <div key={stat.label} className="flex flex-col gap-1 rounded-lg border p-3">
                <span className="text-2xl font-bold tabular-nums text-kpi-emerald">{stat.value}</span>
                <span className="text-xs text-muted-foreground">{stat.label}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {(result.requirements.skills ?? []).slice(0, 6).map((skill) => (
              <Badge key={skill} variant="secondary">
                {skill}
              </Badge>
            ))}
            <Button variant="link" className="ml-auto" nativeButton={false} render={<a href="/demo" />}>
              See every step in the demo
              <ArrowRight data-icon="inline-end" />
            </Button>
          </div>
        </CardFooter>
      ) : null}
    </Card>
  )
}

// ---------------------------------------------------------------------------- content

const PLAN_STAGES: { value: string; label: string; icon: LucideIcon; title: string; points: string[]; code: string }[] = [
  {
    value: "plan",
    label: "1 · Plan",
    icon: FileSearch,
    title: "The Researcher turns a messy post into a plan.",
    points: [
      "Extracts skills, seniority, must-haves and resume-matchable keywords.",
      "Concrete skills only: no soft skills padding the match.",
      "Optional: checks your public GitHub repos for skills the resume doesn't list yet.",
    ],
    code: `{
  "seniority": "Entry-level",
  "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
  "must_haves": ["B.S. in Computer Science", "Python", "FastAPI or Flask"],
  "keywords": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"]
}`,
  },
  {
    value: "check",
    label: "2 · Check",
    icon: ShieldCheck,
    title: "Every tailored line has to show its receipt.",
    points: [
      "The Tailor cites the resume line each rewrite came from.",
      "The Executor verifies each one in code: line match plus every named tool, employer and number.",
      "One unbacked claim blocks every app. No prompt can talk its way past it.",
    ],
    code: `✓ "Built REST APIs in Python using FastAPI"
    source_line: 8   supported: true

✗ "Led a Terraform migration at Google"
    source_line: null   supported: false
    reason: not in original resume: google, terraform`,
  },
  {
    value: "act",
    label: "3 · Act",
    icon: Route,
    title: "Gates first, then the agent picks its tools.",
    points: [
      "Four hard gates run in code before any app is touched.",
      "Only then does the LLM choose which tools to call. It can do less, never skip a gate.",
      "If the model is rate-limited, a rule-based plan takes over and the run still finishes.",
    ],
    code: `gate  keyword overlap ≥ 40%     ✓ 47%
gate  receipts faithful          ✓ 27/27 lines
gate  seniority fits resume      ✓ entry-level
gate  not a duplicate            ✓

plan  create_gmail_draft
      → schedule_followup
      → log_crm_deal
      → notify_slack (always)`,
  },
  {
    value: "loop",
    label: "4 · Close the loop",
    icon: Undo2,
    title: "Apps hand off, replies update everything, undo reverses it.",
    points: [
      "Each app passes what it created to the next, so you get one connected application.",
      "A reply moves the deal, cancels the reminder and pings Slack.",
      "One click undoes the draft, reminder and deal across all apps.",
    ],
    code: `gmail     draft created            → link
calendar  follow-up in 7 days      ← email link
hubspot   deal "drafted"           ← email + event links
slack     one message              ← all three links

reply     deal → replied · reminder cancelled · slack pinged
undo      draft deleted · event deleted · deal closed-lost`,
  },
]

const GATES: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Gauge, title: "Keyword overlap", text: "Below 40% of the job's concrete requirements, nothing is sent and Slack gets the skills gap." },
  { icon: ShieldCheck, title: "Receipts", text: "Any tailored line or cover-note claim the resume can't back blocks every app." },
  { icon: GraduationCap, title: "Seniority", text: "A staff role for a student resume is stopped, however well the keywords match." },
  { icon: CopyX, title: "Duplicates", text: "The same company and role never gets two applications." },
]

const APPS: { key: AppKey; name: string; text: string }[] = [
  { key: "gmail", name: "Gmail", text: "Drafts the email with the tailored resume. Sends only when you allow it and every gate passes." },
  { key: "calendar", name: "Google Calendar", text: "Books a follow-up in 7 days with a link to that email." },
  { key: "crm", name: "HubSpot CRM", text: "Creates a deal for the employer and candidate, carrying both links." },
  { key: "slack", name: "Slack", text: "One message with every link, or why it stopped and what's missing." },
]

const FAQ = [
  {
    q: "Is this actually agentic, or a fixed script?",
    a: "Both, on purpose. The Executor uses LLM tool calling to decide which apps to act in, but the gates that decide whether anything may be sent are code. The model can choose to do less; it can never skip a check. If the model is unavailable, a rule-based plan takes over.",
  },
  {
    q: "Does it ever invent experience?",
    a: "No. The Tailor may only reword existing resume lines and must cite the source line for each. The Executor verifies every line and every named skill, employer and number in code before any app runs.",
  },
  {
    q: "Can I try it without connecting accounts?",
    a: "Yes. The agent console above and /demo run in simulated mode: the real agent pipeline, with apps simulated on the server. Connect Gmail, Calendar, HubSpot and Slack through Composio in the dashboard to act for real.",
  },
  {
    q: "What happens when an app or the model fails?",
    a: "Actions retry transient errors, then report a clear reason; the run finishes as partial instead of crashing. The test suite runs normally and again with Gmail down and the model rate-limited.",
  },
  {
    q: "Does it scrape LinkedIn or Indeed?",
    a: "No. Their terms prohibit it. Live jobs come from public job-board APIs, or you paste any job description.",
  },
]

export function LandingPage() {
  const [summary, setSummary] = useState<{ normal?: EvalSummary; faults?: EvalSummary }>({})

  useEffect(() => {
    document.title = "Honest Apply · The job agent that won't lie for you"
    api<{ normal?: EvalSummary; faults?: EvalSummary }>("/api/eval/summary").then(setSummary).catch(() => undefined)
  }, [])

  const score = (s?: EvalSummary) => (s ? `${s.passed}/${s.total}` : "—")

  return (
    <div className="demo-theme-dark min-h-svh bg-background text-foreground">
      <header className="fixed inset-x-4 top-4 z-50 mx-auto max-w-6xl rounded-xl border bg-card/80 backdrop-blur">
        <nav className="flex items-center gap-2 px-4 py-2.5" aria-label="Main">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck aria-hidden="true" />
            </span>
            Honest Apply
          </a>
          <div className="ml-auto hidden items-center gap-1 md:flex">
            {[
              ["#planning", "How it plans"],
              ["#gates", "Gates"],
              ["#apps", "Apps"],
              ["#proof", "Proof"],
              ["#faq", "FAQ"],
            ].map(([href, label]) => (
              <LinkButton key={href} href={href} variant="ghost" size="sm">
                {label}
              </LinkButton>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-2 md:ml-2">
            <LinkButton href="/demo" variant="outline" size="default">
              Demo
            </LinkButton>
            <LinkButton href="/app" size="default">
              Dashboard
            </LinkButton>
          </div>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pt-32 pb-20 lg:grid-cols-[1fr_1.05fr] lg:pt-40">
          <Reveal className="flex flex-col items-start gap-6">
            <Badge variant="outline" className="h-7 gap-2 px-3">
              <span className="size-2 rounded-full bg-kpi-emerald" aria-hidden="true" />
              Agentic job applications with receipts
            </Badge>
            <h1 className="text-5xl font-bold tracking-tight text-balance sm:text-6xl lg:text-7xl">
              The job agent that <span className="text-kpi-emerald">won't lie</span> for you.
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-pretty text-muted-foreground">
              Three agents plan the application, prove every line against your real resume, then act across Gmail, Google Calendar,
              HubSpot and Slack. Press <span className="text-foreground">Watch it plan</span> to see a real run.
            </p>
            <div className="flex flex-wrap gap-3">
              <LinkButton href="/demo">
                Open the demo
                <ArrowRight data-icon="inline-end" />
              </LinkButton>
              <LinkButton href={REPO} variant="outline">
                <FolderGit2 data-icon="inline-start" />
                Source on GitHub
              </LinkButton>
            </div>
            <div className="grid w-full max-w-xl grid-cols-3 gap-3 pt-2">
              {[
                { value: "3", label: "agents" },
                { value: "4", label: "apps that hand off" },
                { value: score(summary.faults), label: "tests passed with failures injected" },
              ].map((stat) => (
                <div key={stat.label} className="flex flex-col gap-1">
                  <span className="text-3xl font-bold tabular-nums text-kpi-yellow">{stat.value}</span>
                  <span className="text-sm leading-snug text-muted-foreground">{stat.label}</span>
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <AgentConsole />
          </Reveal>
        </section>

        <section id="planning" className="scroll-mt-24 border-y bg-card/40 px-4 py-24">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="How the agent plans"
                title="Plan, check, act, close the loop."
                description="The model plans and chooses tools. Code decides whether anything may happen. Here's what each stage actually produces."
              />
            </Reveal>
            <Reveal>
              <Tabs defaultValue="plan" className="gap-6">
                <TabsList className="flex h-auto w-full flex-wrap justify-start">
                  {PLAN_STAGES.map((stage) => (
                    <TabsTrigger key={stage.value} value={stage.value} className="gap-2">
                      <stage.icon aria-hidden="true" />
                      {stage.label}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {PLAN_STAGES.map((stage) => (
                  <TabsContent key={stage.value} value={stage.value}>
                    <div className="grid items-start gap-6 lg:grid-cols-[1fr_1.1fr]">
                      <div className="flex flex-col gap-5">
                        <h3 className="text-2xl font-semibold tracking-tight text-balance">{stage.title}</h3>
                        <ul className="flex flex-col gap-3">
                          {stage.points.map((point) => (
                            <li key={point} className="flex gap-3 leading-relaxed text-muted-foreground">
                              <Check className="mt-1 shrink-0 text-kpi-emerald" aria-hidden="true" />
                              {point}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <Card>
                        <CardContent>
                          <pre className="overflow-x-auto font-mono text-sm leading-relaxed whitespace-pre text-foreground">{stage.code}</pre>
                        </CardContent>
                      </Card>
                    </div>
                  </TabsContent>
                ))}
              </Tabs>
            </Reveal>
          </div>
        </section>

        <section id="gates" className="scroll-mt-24 px-4 py-24">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="Four hard gates"
                title="Nothing reaches an app until all four pass."
                description="They live in code, not in a prompt. When one fails, the agent stops and tells you exactly why."
              />
            </Reveal>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {GATES.map((gate, i) => (
                <Reveal key={gate.title} delay={i * 0.06}>
                  <Card className="h-full">
                    <CardHeader>
                      <IconTile icon={gate.icon} tone="yellow" />
                      <CardTitle>{gate.title}</CardTitle>
                      <CardDescription className="leading-relaxed">{gate.text}</CardDescription>
                    </CardHeader>
                  </Card>
                </Reveal>
              ))}
            </div>
            <Reveal>
              <div className="grid gap-4 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Typical auto-apply bot</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3 text-sm">
                    {["Stuffs in skills you don't have", "Sends emails you never read", "Loses track of where you applied", "Fails silently"].map((item) => (
                      <span key={item} className="flex gap-3">
                        <X className="shrink-0 text-destructive" aria-hidden="true" />
                        {item}
                      </span>
                    ))}
                  </CardContent>
                </Card>
                <Card className="border-kpi-emerald/40">
                  <CardHeader>
                    <CardTitle>Honest Apply</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3 text-sm">
                    {[
                      "Every line cites your resume or a public GitHub repo",
                      "Drafts by default; sends only when you allow it",
                      "Every application in HubSpot with a follow-up booked",
                      "Retries, falls back or flags, and says why in Slack",
                    ].map((item) => (
                      <span key={item} className="flex gap-3">
                        <Check className="shrink-0 text-kpi-emerald" aria-hidden="true" />
                        {item}
                      </span>
                    ))}
                  </CardContent>
                </Card>
              </div>
            </Reveal>
          </div>
        </section>

        <section id="apps" className="scroll-mt-24 border-y bg-card/40 px-4 py-24">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="Apps that work together"
                title="Not four integrations. One hand-off."
                description="Each app passes what it created to the next. Connect your own accounts in one click through Composio, or run everything simulated."
              />
            </Reveal>
            <div className="grid gap-4 lg:grid-cols-4">
              {APPS.map((app, i) => {
                const Icon = APP_ICONS[app.key]
                return (
                  <Reveal key={app.key} delay={i * 0.06} className="relative">
                    <Card className="h-full">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <IconTile icon={Icon} />
                          <Badge variant="outline">Step {i + 1}</Badge>
                        </div>
                        <CardTitle>{app.name}</CardTitle>
                        <CardDescription className="leading-relaxed">{app.text}</CardDescription>
                      </CardHeader>
                    </Card>
                    {i < APPS.length - 1 ? (
                      <ArrowRight className="absolute top-1/2 -right-3.5 z-10 hidden -translate-y-1/2 text-kpi-emerald lg:block" aria-hidden="true" />
                    ) : null}
                  </Reveal>
                )
              })}
            </div>
            <Reveal>
              <Card className="border-kpi-yellow/40">
                <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  <IconTile icon={Mail} tone="yellow" />
                  <p className="leading-relaxed">
                    <span className="font-semibold">When they reply:</span> the HubSpot deal moves to Replied, the follow-up cancels itself, and
                    Slack pings you. <span className="text-muted-foreground">Changed your mind? One click undoes every app.</span>
                  </p>
                </CardContent>
              </Card>
            </Reveal>
          </div>
        </section>

        <section id="proof" className="scroll-mt-24 px-4 py-24">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="Show how you know it works"
                title="We break it on purpose."
                description="Ten job descriptions, including a poor fit and one built to bait fabrication, scored on four checks. Then again with Gmail down and the model rate-limited."
              />
            </Reveal>
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                { value: score(summary.normal), label: "test jobs passed, normal run", tone: "text-kpi-emerald" },
                { value: score(summary.faults), label: "passed with Gmail down and the LLM rate-limited", tone: "text-kpi-emerald" },
                { value: "0", label: "real accounts touched by simulated runs", tone: "text-kpi-yellow" },
              ].map((stat, i) => (
                <Reveal key={stat.label} delay={i * 0.06}>
                  <Card className="h-full">
                    <CardHeader>
                      <CardTitle className={`text-6xl font-bold tabular-nums ${stat.tone}`}>{stat.value}</CardTitle>
                      <CardDescription className="text-base">{stat.label}</CardDescription>
                    </CardHeader>
                  </Card>
                </Reveal>
              ))}
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                { icon: FlaskConical, title: "Chaos panel", text: "Switch off Gmail, Calendar, HubSpot, Slack or the model and watch retries, fallbacks and clear failures." },
                { icon: Undo2, title: "One-click undo", text: "Deletes the draft and reminder, closes the deal and tells Slack, across every app at once." },
                { icon: FolderGit2, title: "Open and reproducible", text: "The eval suite, self-checks and simulated demo all run from a fresh clone with no keys." },
              ].map((item, i) => (
                <Reveal key={item.title} delay={i * 0.06}>
                  <Card className="h-full">
                    <CardHeader>
                      <IconTile icon={item.icon} />
                      <CardTitle>{item.title}</CardTitle>
                      <CardDescription className="leading-relaxed">{item.text}</CardDescription>
                    </CardHeader>
                  </Card>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="border-y bg-card/40 px-4 py-24">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading eyebrow="Who it's for" title="Built for one, ready for a team." description="The same agent, wherever applications and placements happen." />
            </Reveal>
            <div className="grid gap-4 md:grid-cols-3">
              {[
                { icon: BriefcaseBusiness, title: "Job seekers", text: "Honest, tailored applications at volume, with the follow-up already booked." },
                { icon: GraduationCap, title: "Career centers", text: "Coaches see every student's pipeline in HubSpot and get skill gaps in Slack." },
                { icon: Users, title: "Staffing agencies", text: "Submit candidates faster, and nothing goes out with a claim the resume can't back." },
              ].map((item, i) => (
                <Reveal key={item.title} delay={i * 0.06}>
                  <Card className="h-full">
                    <CardHeader>
                      <IconTile icon={item.icon} />
                      <CardTitle>{item.title}</CardTitle>
                      <CardDescription className="leading-relaxed">{item.text}</CardDescription>
                    </CardHeader>
                  </Card>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="scroll-mt-24 px-4 py-24">
          <div className="mx-auto flex max-w-3xl flex-col gap-10">
            <Reveal>
              <SectionHeading eyebrow="FAQ" title="Straight answers." description="What it does, what it won't do, and what happens when things break." />
            </Reveal>
            <Reveal>
              <Accordion>
                {FAQ.map((item) => (
                  <AccordionItem key={item.q} value={item.q}>
                    <AccordionTrigger className="text-base">{item.q}</AccordionTrigger>
                    <AccordionContent>
                      <p className="leading-relaxed text-muted-foreground">{item.a}</p>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </Reveal>
          </div>
        </section>

        <section className="px-4 pb-24">
          <Reveal className="mx-auto max-w-6xl">
            <Card className="border-kpi-emerald/40 bg-card">
              <CardContent className="flex flex-col items-center gap-6 py-10 text-center">
                <IconTile icon={Bot} />
                <h2 className="max-w-2xl text-3xl font-bold tracking-tight text-balance sm:text-5xl">Apply to more jobs without lowering the bar.</h2>
                <p className="max-w-xl text-lg text-muted-foreground">Walk through every step in the demo, or open the dashboard and connect your own apps.</p>
                <div className="flex flex-wrap justify-center gap-3">
                  <LinkButton href="/demo">
                    Open the demo
                    <ArrowRight data-icon="inline-end" />
                  </LinkButton>
                  <LinkButton href="/app" variant="outline">
                    <LayoutDashboard data-icon="inline-start" />
                    Open the dashboard
                  </LinkButton>
                </div>
              </CardContent>
            </Card>
          </Reveal>
        </section>
      </main>

      <footer className="border-t px-4 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 text-sm text-muted-foreground sm:flex-row">
          <span>Built for the Multi-App AI Agent Hackathon · September 2026</span>
          <Separator orientation="vertical" className="hidden h-4 sm:block" />
          <a className="hover:text-foreground" href={REPO}>
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
