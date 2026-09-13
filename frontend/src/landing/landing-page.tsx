import { motion } from "framer-motion"
import type { LucideIcon } from "lucide-react"
import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Building2,
  CalendarClock,
  Check,
  FileSearch,
  FlaskConical,
  FolderGit2,
  GraduationCap,
  Mail,
  MessageSquare,
  PenLine,
  ShieldCheck,
  Undo2,
  Users,
  X,
} from "lucide-react"
import type { ReactNode } from "react"
import { useEffect, useState } from "react"

import { api } from "@/app/api"
import type { EvalSummary, HistoryRow } from "@/app/types"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

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
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
      <Badge variant="secondary">{eyebrow}</Badge>
      <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{title}</h2>
      <p className="text-base leading-relaxed text-pretty text-muted-foreground">{description}</p>
    </div>
  )
}

function IconTile({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
      <Icon aria-hidden="true" />
    </span>
  )
}

const NAV = [
  { href: "#how", label: "How it works" },
  { href: "#apps", label: "Apps" },
  { href: "#proof", label: "Proof" },
  { href: "#faq", label: "FAQ" },
]

const AGENTS: { icon: LucideIcon; name: string; text: string }[] = [
  { icon: FileSearch, name: "Researcher", text: "Turns a messy job post into structured requirements: skills, seniority, must-haves and keywords." },
  { icon: PenLine, name: "Tailor", text: "Rewrites your resume and cover note from lines you already have, citing the source line for each one." },
  { icon: ShieldCheck, name: "Executor", text: "Checks every receipt in code, then picks which apps to act in. It can do less, never skip a gate." },
]

const APPS: { icon: LucideIcon; name: string; text: string }[] = [
  { icon: Mail, name: "Gmail", text: "Drafts the email with your tailored resume. Sends only when you allow it and every check passes." },
  { icon: CalendarClock, name: "Google Calendar", text: "Books a follow-up in 7 days, linked to that email." },
  { icon: Building2, name: "HubSpot CRM", text: "Creates a deal linked to the employer and the candidate, carrying both links." },
  { icon: MessageSquare, name: "Slack", text: "One message with every link, or why it stopped and what you're missing." },
]

const GUARANTEES: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Check, title: "Receipts", text: "Every tailored line traces to your resume or a public GitHub repo. No source, no send." },
  { icon: ShieldCheck, title: "Hard gates", text: "Low overlap, an unbacked claim, a seniority mismatch or a repeat application stops the agent before any app." },
  { icon: FlaskConical, title: "Chaos-tested", text: "Switch off Gmail, HubSpot, Slack or the model on purpose. It retries, falls back or flags. It doesn't crash." },
  { icon: Undo2, title: "One-click undo", text: "Deletes the draft and the reminder, closes the CRM deal, and tells Slack. Across every app at once." },
]

const FAQ = [
  {
    q: "Does it ever invent experience?",
    a: "No. The Tailor may only reword lines from your resume, and the Executor checks every line in code before anything is sent. Skills can come from your public GitHub repos, and those lines name the repo as the source.",
  },
  {
    q: "Will it send applications without me?",
    a: "Not by default. Everything is a Gmail draft. Sending needs your connected Gmail, your Allow sending switch, a recipient, a strong match and a clean receipts check, all at once.",
  },
  {
    q: "Which apps does it use, and how do I connect them?",
    a: "Gmail, Google Calendar, HubSpot and Slack. In the dashboard you enter your email and click Connect for each; Composio handles the sign-in and stores the tokens.",
  },
  {
    q: "What happens when an app or the AI model fails?",
    a: "Actions retry transient errors, then report a clear reason. If the model is rate-limited, each agent falls back to a rule-based mode and the run still completes. The Reliability page runs the full test suite with failures switched on.",
  },
  {
    q: "Does it search LinkedIn or Indeed?",
    a: "No. Their terms prohibit scraping. Live jobs come from public job-board APIs (Arbeitnow, Remotive, RemoteOK), or you paste any job description.",
  },
]

const DashboardButton = ({ children, size = "lg" }: { children: ReactNode; size?: "lg" | "default" }) => (
  <Button size={size} nativeButton={false} render={<a href="/app" />}>
    {children}
    <ArrowRight data-icon="inline-end" />
  </Button>
)

export function LandingPage() {
  const [stats, setStats] = useState<{ normal?: EvalSummary; faults?: EvalSummary; runs?: number }>({})

  useEffect(() => {
    document.title = "Honest Apply · The job agent that won't lie for you"
    api<{ normal?: EvalSummary; faults?: EvalSummary }>("/api/eval/summary")
      .then((summary) => setStats((s) => ({ ...s, ...summary })))
      .catch(() => undefined)
    api<HistoryRow[]>("/api/history")
      .then((rows) => setStats((s) => ({ ...s, runs: rows.length })))
      .catch(() => undefined)
  }, [])

  const score = (summary?: EvalSummary) => (summary ? `${summary.passed}/${summary.total}` : "—")

  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="fixed inset-x-4 top-4 z-50 mx-auto max-w-6xl rounded-xl border bg-card/90 shadow-sm backdrop-blur">
        <nav className="flex items-center gap-4 px-4 py-2.5" aria-label="Main">
          <a href="/" className="flex items-center gap-2 font-semibold">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck aria-hidden="true" />
            </span>
            Honest Apply
          </a>
          <div className="ml-auto hidden items-center gap-1 md:flex">
            {NAV.map((item) => (
              <Button key={item.href} variant="ghost" size="sm" nativeButton={false} render={<a href={item.href} />}>
                {item.label}
              </Button>
            ))}
          </div>
          <div className="ml-auto md:ml-2">
            <DashboardButton size="default">Open dashboard</DashboardButton>
          </div>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pt-32 pb-20 lg:grid-cols-[1.1fr_1fr] lg:pt-40">
          <Reveal className="flex flex-col items-start gap-6">
            <Badge variant="secondary">3 agents · 4 connected apps · 0 invented claims</Badge>
            <h1 className="text-4xl font-bold tracking-tight text-balance sm:text-5xl lg:text-6xl">
              The job agent that <span className="text-primary">won't lie</span> for you.
            </h1>
            <p className="max-w-xl text-lg leading-relaxed text-pretty text-muted-foreground">
              Paste a job or pick a live one. Three agents tailor your real experience to it, prove every line, and only then act
              across Gmail, Google Calendar, HubSpot and Slack.
            </p>
            <div className="flex flex-wrap gap-3">
              <DashboardButton>Open the dashboard</DashboardButton>
              <Button size="lg" variant="outline" nativeButton={false} render={<a href="#proof" />}>
                See how it's tested
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">Drafts by default. Undo everything in one click.</p>
          </Reveal>

          <Reveal delay={0.1}>
            <Card className="shadow-lg">
              <CardHeader>
                <CardDescription>Example run</CardDescription>
                <CardTitle>Backend Engineer at a fintech startup</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="grid gap-2 sm:grid-cols-3">
                  {AGENTS.map((agent) => (
                    <div key={agent.name} className="flex items-center gap-2 rounded-lg border p-2 text-sm">
                      <agent.icon className="text-primary" aria-hidden="true" />
                      <span className="font-medium">{agent.name}</span>
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {APPS.map((app, i) => (
                    <div key={app.name} className="flex items-center gap-2">
                      <Badge>{app.name}</Badge>
                      {i < APPS.length - 1 ? <ArrowRight className="text-muted-foreground" aria-hidden="true" /> : null}
                    </div>
                  ))}
                </div>
                <Separator />
                <div className="flex flex-col gap-3 text-sm">
                  <div className="flex items-start gap-3">
                    <Badge variant="outline">line 8</Badge>
                    <div className="flex flex-col gap-0.5">
                      <span>Built REST APIs in Python with FastAPI and PostgreSQL</span>
                      <span className="text-xs text-muted-foreground">Receipt: matches your resume</span>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Badge variant="outline">GitHub</Badge>
                    <div className="flex flex-col gap-0.5">
                      <span>Kubernetes, shown in a public repo</span>
                      <span className="text-xs text-muted-foreground">Receipt: the repo link is on the resume line</span>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Badge variant="destructive">blocked</Badge>
                    <div className="flex flex-col gap-0.5">
                      <span className="line-through decoration-destructive/60">Led a Terraform migration at Google</span>
                      <span className="text-xs text-destructive">Not in your resume, so nothing is sent</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Reveal>
        </section>

        <section className="border-y bg-card/60 px-4 py-20">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="Before and after"
                title="Auto-apply bots trade your credibility for volume."
                description="Honest Apply keeps the volume and removes the risk."
              />
            </Reveal>
            <div className="grid gap-6 md:grid-cols-2">
              <Reveal>
                <Card className="h-full">
                  <CardHeader>
                    <CardTitle>Typical auto-apply bot</CardTitle>
                    <CardDescription>Fast, and quietly damaging</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ul className="flex flex-col gap-3 text-sm">
                      {[
                        "Stuffs in skills you don't have to match keywords",
                        "Sends hundreds of emails you never read",
                        "Loses track of who you applied to and when",
                        "Fails silently when an app breaks",
                      ].map((item) => (
                        <li key={item} className="flex gap-3">
                          <X className="shrink-0 text-destructive" aria-hidden="true" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </Reveal>
              <Reveal delay={0.1}>
                <Card className="h-full border-primary/40 shadow-md">
                  <CardHeader>
                    <CardTitle>Honest Apply</CardTitle>
                    <CardDescription>Just as fast, and every line holds up</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ul className="flex flex-col gap-3 text-sm">
                      {[
                        "Every line cites your resume or a public GitHub repo",
                        "Drafts by default; sends only when you allow it and every check passes",
                        "Every application lands in HubSpot with a follow-up on your calendar",
                        "Retries, falls back or flags, and tells you why in Slack",
                      ].map((item) => (
                        <li key={item} className="flex gap-3">
                          <Check className="shrink-0 text-primary" aria-hidden="true" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </Reveal>
            </div>
          </div>
        </section>

        <section id="how" className="scroll-mt-24 px-4 py-20">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="How it works"
                title="One agent, three stages, hard gates in between."
                description="The rules that decide whether anything is sent live in code, not in a prompt the model could talk its way around."
              />
            </Reveal>
            <div className="grid gap-6 md:grid-cols-3">
              {AGENTS.map((agent, i) => (
                <Reveal key={agent.name} delay={i * 0.08}>
                  <Card className="h-full">
                    <CardHeader>
                      <div className="flex items-center gap-3">
                        <IconTile icon={agent.icon} />
                        <Badge variant="outline">Step {i + 1}</Badge>
                      </div>
                      <CardTitle>{agent.name}</CardTitle>
                      <CardDescription className="leading-relaxed">{agent.text}</CardDescription>
                    </CardHeader>
                  </Card>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="apps" className="scroll-mt-24 border-y bg-card/60 px-4 py-20">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="Apps that work together"
                title="Not four integrations. One hand-off."
                description="Each app passes what it made to the next, so you get one connected application instead of four scattered side effects."
              />
            </Reveal>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {APPS.map((app, i) => (
                <Reveal key={app.name} delay={i * 0.06}>
                  <Card className="h-full">
                    <CardHeader>
                      <IconTile icon={app.icon} />
                      <CardTitle>{app.name}</CardTitle>
                      <CardDescription className="leading-relaxed">{app.text}</CardDescription>
                    </CardHeader>
                  </Card>
                </Reveal>
              ))}
            </div>
            <Reveal>
              <Card className="border-primary/40">
                <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  <IconTile icon={Mail} />
                  <p className="text-sm leading-relaxed">
                    <span className="font-semibold">When they reply:</span> Gmail spots it, the HubSpot deal moves to Replied, the
                    follow-up reminder cancels itself, and Slack pings you with the link.
                  </p>
                </CardContent>
              </Card>
            </Reveal>
          </div>
        </section>

        <section id="proof" className="scroll-mt-24 px-4 py-20">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="Show how you know it works"
                title="We break it on purpose."
                description="Ten job descriptions, including a poor fit and one built to bait fabrication, scored on four checks. Then again with Gmail down and the model rate-limited."
              />
            </Reveal>
            <div className="grid gap-6 sm:grid-cols-3">
              {[
                { value: score(stats.normal), label: "test jobs passed, normal run" },
                { value: score(stats.faults), label: "passed with Gmail down and the LLM rate-limited" },
                { value: stats.runs === undefined ? "—" : String(stats.runs), label: "agent runs logged" },
              ].map((stat, i) => (
                <Reveal key={stat.label} delay={i * 0.06}>
                  <Card className="h-full">
                    <CardHeader>
                      <CardTitle className="text-4xl font-bold tabular-nums text-primary">{stat.value}</CardTitle>
                      <CardDescription>{stat.label}</CardDescription>
                    </CardHeader>
                  </Card>
                </Reveal>
              ))}
            </div>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {GUARANTEES.map((item, i) => (
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

        <section className="border-y bg-card/60 px-4 py-20">
          <div className="mx-auto flex max-w-6xl flex-col gap-10">
            <Reveal>
              <SectionHeading
                eyebrow="Built for one, ready for a team"
                title="The same agent, wherever placements happen."
                description="Deals land in the CRM and updates land in Slack, so the people who help candidates see every application."
              />
            </Reveal>
            <div className="grid gap-6 md:grid-cols-3">
              {[
                { icon: BriefcaseBusiness, title: "Job seekers", text: "Tailored, honest applications at volume, with the follow-up already on your calendar." },
                { icon: GraduationCap, title: "Career centers", text: "Coaches see each student's pipeline in HubSpot and get skill gaps in Slack before they turn into rejections." },
                { icon: Users, title: "Staffing agencies", text: "Recruiters submit candidates faster, and nothing goes out with a claim the resume can't back." },
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

        <section id="faq" className="scroll-mt-24 px-4 py-20">
          <div className="mx-auto flex max-w-3xl flex-col gap-10">
            <Reveal>
              <SectionHeading eyebrow="FAQ" title="Straight answers." description="What it does, what it won't do, and what happens when things break." />
            </Reveal>
            <Reveal>
              <Accordion>
                {FAQ.map((item) => (
                  <AccordionItem key={item.q} value={item.q}>
                    <AccordionTrigger>{item.q}</AccordionTrigger>
                    <AccordionContent>
                      <p className="leading-relaxed text-muted-foreground">{item.a}</p>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </Reveal>
          </div>
        </section>

        <section className="px-4 pb-20">
          <Reveal className="mx-auto max-w-6xl">
            <Card className="bg-primary text-primary-foreground">
              <CardContent className="flex flex-col items-center gap-6 py-6 text-center">
                <IconTile icon={Bot} />
                <h2 className="text-3xl font-semibold tracking-tight text-balance">Apply to more jobs without lowering the bar.</h2>
                <p className="max-w-xl text-primary-foreground/85">
                  Connect your apps, add your GitHub, pick your matches. Every application stays honest, tracked and reversible.
                </p>
                <Button size="lg" variant="secondary" nativeButton={false} render={<a href="/app" />}>
                  Open the dashboard
                  <ArrowRight data-icon="inline-end" />
                </Button>
              </CardContent>
            </Card>
          </Reveal>
        </section>
      </main>

      <footer className="border-t px-4 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 text-sm text-muted-foreground sm:flex-row">
          <span className="flex items-center gap-2">
            <FolderGit2 aria-hidden="true" />
            Built for the Multi-App AI Agent Hackathon · September 2026
          </span>
          <a className="hover:text-foreground" href="https://github.com/charansaiponnada/honest-apply">
            Source on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
