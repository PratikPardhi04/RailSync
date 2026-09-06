import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  TrainFront, Sparkles, ShieldCheck, Clock, GitBranch, Radio,
  Users, ArrowRight, CircuitBoard, LineChart, Workflow, MapPin,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import AgentWorkflowDemo from '../components/AgentWorkflowDemo'

const FEATURES = [
  {
    icon: Sparkles,
    title: 'AI-Optimized Windows',
    text: 'LangGraph agents analyze traffic, priority and maintenance rules to recommend the least-impact block window on busy rail corridors.',
  },
  {
    icon: CircuitBoard,
    title: 'Deterministic CP-SAT Solver',
    text: 'Google OR-Tools picks the safest schedule. AI proposes, mathematical optimization decides — officers never approve an unsafe plan.',
  },
  {
    icon: ShieldCheck,
    title: 'Auto-Replan on Conflicts',
    text: 'Hard conflicts with premium trains (Rajdhani, Shatabdi, Vande Bharat) trigger an automatic replan before anything reaches the officer.',
  },
  {
    icon: LineChart,
    title: 'Risk & Confidence Scores',
    text: 'Every plan ships with risk, delay and confidence metrics plus a live simulation of affected trains on the section.',
  },
  {
    icon: GitBranch,
    title: 'Versioned Reports',
    text: 'Full audit trail of plan versions, officer decisions, agent reasoning and block execution history across the corridor.',
  },
  {
    icon: Radio,
    title: 'Live Operational View',
    text: 'Watch the simulated railway in real time — trains dispatched, blocks active, delays tracked as the network operates.',
  },
]

const STEPS = [
  {
    icon: Users,
    title: 'Engineer Raises a Block Request',
    text: 'Section, track, work type, preferred window and maintenance instructions are submitted through the engineer portal.',
  },
  {
    icon: Workflow,
    title: 'Agentic Pipeline Plans It',
    text: 'Nine specialised agents validate, analyze, generate candidates, optimize with CP-SAT, simulate and validate constraints.',
  },
  {
    icon: ShieldCheck,
    title: 'Officer Reviews & Approves',
    text: 'The generated report lands in the officer queue with risk and confidence scores. Approve, or reject with feedback to trigger a live replan.',
  },
]

export default function Landing() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const enterPortal = () => {
    if (user) {
      navigate(user.role === 'officer' ? '/officer' : '/engineer')
    } else {
      navigate('/login')
    }
  }

  return (
    <div className="min-h-screen rail-canvas bg-so-bg text-so-text">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/90 backdrop-blur">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="relative w-9 h-9 rounded-xl bg-railway-blue/10 border border-railway-blue/20 flex items-center justify-center">
                <TrainFront className="w-5 h-5 text-railway-accent" />
                <span className="absolute inset-0 rounded-xl bg-blue-400/20 animate-pulse" />
              </div>
              <div>
                <h1 className="text-base font-extrabold tracking-tight">
                  <span className="text-railway-darkblue">RailSync</span>{' '}
                  <span className="text-railway-accent">AI</span>
                </h1>
                <p className="text-[11px] text-gray-500 -mt-0.5">Railway Block Planning</p>
              </div>
            </div>
            <nav className="hidden md:flex items-center gap-8 text-sm text-gray-600">
              <a href="#features" className="hover:text-railway-accent transition-colors font-medium">Features</a>
              <a href="#how-it-works" className="hover:text-railway-accent transition-colors font-medium">How it works</a>
              <a href="#workflow" className="hover:text-railway-accent transition-colors font-medium">The Agent</a>
              <a href="#demo" className="hover:text-railway-accent transition-colors font-medium">Demo</a>
              <button
                onClick={enterPortal}
                className="bg-railway-accent hover:bg-railway-blue text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              >
                {user ? 'Enter Portal' : 'Sign In'}
              </button>
            </nav>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-28">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center max-w-3xl mx-auto"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-railway-accent/30 bg-railway-accent/5 px-4 py-1.5 text-xs font-semibold text-railway-accent mb-6">
            <Sparkles className="w-3.5 h-3.5" />
            AI-Powered Maintenance Block Planning
          </div>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-tight text-gray-900">
            Smart railway blocks,{' '}
            <span className="text-railway-accent">zero schedule chaos.</span>
          </h2>
          <p className="text-lg text-gray-600 mt-6 leading-relaxed max-w-2xl mx-auto">
            RailSync AI analyzes the congested Pune–Mumbai corridor, generates
            least-impact maintenance block plans, and lets officers approve with
            confidence — all in one platform.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 mt-10">
            <button
              onClick={enterPortal}
              className="btn-rail text-base px-8 py-3"
            >
              {user ? 'Enter Portal' : 'Request a Block'} <ArrowRight className="w-4 h-4" />
            </button>
            <a
              href="#how-it-works"
              className="btn-ghost px-8 py-3"
            >
              <Workflow className="w-4 h-4" /> See How It Works
            </a>
          </div>

          {/* Quick stat strip */}
          <div className="grid grid-cols-3 gap-4 mt-16 max-w-2xl mx-auto">
            {[
              { value: '9', label: 'Specialist Agents' },
              { value: '<10min', label: 'Typical Replan' },
              { value: '100%', label: 'Conflict Auto-Screen' },
            ].map((s) => (
              <div key={s.label} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
                <p className="text-2xl sm:text-3xl font-extrabold text-railway-accent">{s.value}</p>
                <p className="text-xs text-gray-500 mt-1">{s.label}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-gray-200 bg-gray-50 py-20">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h3 className="text-3xl font-extrabold text-gray-900">Built for ground reality</h3>
            <p className="text-gray-600 mt-3 max-w-xl mx-auto">
              Premium trains don't wait. Every block is screened, simulated and versioned before it reaches the officer.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm hover:border-railway-accent/40 transition-colors"
              >
                <div className="w-10 h-10 rounded-xl bg-railway-accent/10 border border-railway-accent/20 flex items-center justify-center mb-4">
                  <f.icon className="w-5 h-5 text-railway-accent" />
                </div>
                <h4 className="font-bold text-lg text-gray-900">{f.title}</h4>
                <p className="text-sm text-gray-600 mt-2 leading-relaxed">{f.text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="py-20">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h3 className="text-3xl font-extrabold text-gray-900">How it works</h3>
            <p className="text-gray-600 mt-3 max-w-xl mx-auto">
              From engineering request to published block — a transparent, auditable pipeline.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {STEPS.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="relative rounded-2xl border border-gray-200 bg-white p-6 shadow-sm"
              >
                <div className="absolute -top-3 left-6 w-8 h-8 rounded-full bg-railway-accent text-white text-sm font-bold flex items-center justify-center">
                  {i + 1}
                </div>
                <div className="w-10 h-10 rounded-xl bg-railway-accent/10 border border-railway-accent/20 flex items-center justify-center mb-4 mt-2">
                  <s.icon className="w-5 h-5 text-railway-accent" />
                </div>
                <h4 className="font-bold text-lg text-gray-900">{s.title}</h4>
                <p className="text-sm text-gray-600 mt-2 leading-relaxed">{s.text}</p>
                {i < STEPS.length - 1 && (
                  <ArrowRight className="hidden md:block absolute top-1/2 -right-4 w-5 h-5 text-railway-accent/70" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Agent workflow demo */}
      <section id="workflow" className="border-t border-gray-200 bg-gray-50 py-20">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
          <AgentWorkflowDemo />
        </div>
      </section>

      {/* Demo CTA */}
      <section id="demo" className="border-t border-gray-200 bg-gray-50 py-20">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <MapPin className="w-10 h-10 text-railway-accent mx-auto mb-4" />
          <h3 className="text-3xl font-extrabold text-gray-900">Explore the Pune–Mumbai corridor live</h3>
          <p className="text-gray-600 mt-3 max-w-xl mx-auto">
            Jump into the demo with one click. See real agent-generated reports, risk assessments, and live train operations.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 mt-8">
            <Link to="/login" className="btn-rail text-base px-8 py-3">
              <Clock className="w-4 h-4" /> Login to Demo
            </Link>
            <button
              onClick={enterPortal}
              className="btn-ghost px-8 py-3"
            >
              {user ? 'Enter Portal' : 'Continue to Dashboard'} <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-8">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <TrainFront className="w-4 h-4" />
            RailSync AI — Railway Maintenance Block Planning System
          </div>
          <p className="text-xs text-gray-400">
            Prototype / simulated data. Not for live railway operations.
          </p>
        </div>
      </footer>
    </div>
  )
}