import { useEffect, useState } from 'react'
import type { AppRoute } from '../types/navigation'

interface LandingPageProps {
  onNavigate: (destination: AppRoute) => void
}

const features = [
  {
    icon: '✦',
    title: 'DeskAI Assistant',
    description: 'Resolve everyday IT questions through a helpful, natural conversation.',
    tone: 'violet',
  },
  {
    icon: '⌕',
    title: 'Knowledge-Powered Answers',
    description: 'Ground responses in your organization’s trusted support knowledge.',
    tone: 'blue',
  },
  {
    icon: '◈',
    title: 'Incident Classification',
    description: 'Understand urgency, category, and the right team with every request.',
    tone: 'amber',
  },
  {
    icon: '↗',
    title: 'Ticket Automation',
    description: 'Turn support conversations into actionable service desk tickets.',
    tone: 'mint',
  },
  {
    icon: '◎',
    title: 'Human Agent Escalation',
    description: 'Bring a service professional into the conversation when needed.',
    tone: 'rose',
  },
  {
    icon: '▥',
    title: 'Analytics Dashboard',
    description: 'See ticket trends, workload, priorities, and service desk health.',
    tone: 'indigo',
  },
]

const steps = [
  ['01', 'Ask a question', 'Describe the issue in your own words.'],
  ['02', 'Search knowledge', 'DeskAI finds relevant, trusted guidance.'],
  ['03', 'Classify the issue', 'Understand category, impact, and priority.'],
  ['04', 'Create a ticket', 'Capture the details for clear follow-through.'],
  ['05', 'Escalate to a human', 'Connect with an agent whenever it helps.'],
]

const benefits = [
  ['Resolve faster', 'Give people helpful answers without making them wait.'],
  ['Stay knowledge driven', 'Make support guidance easier to find and reuse.'],
  ['Route intelligently', 'Get every issue to the right team with useful context.'],
  ['Work together', 'Keep AI assistance and human expertise in one experience.'],
]

function BrandMark() {
  return (
    <span className="landing-brand-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32">
        <path d="M16 3.5 19.1 12l8.4 4-8.4 3.1L16 28.5 12.9 19l-8.4-3 8.4-4L16 3.5Z" />
        <path d="m25.5 3 .9 2.6L29 6.5l-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z" />
      </svg>
    </span>
  )
}

export function LandingPage({ onNavigate }: LandingPageProps) {
  const [isRoleSelectionOpen, setIsRoleSelectionOpen] = useState(false)

  useEffect(() => {
    if (!isRoleSelectionOpen) return

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setIsRoleSelectionOpen(false)
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isRoleSelectionOpen])

  function openRoleSelection() {
    setIsRoleSelectionOpen(true)
  }

  return (
    <div className="landing-page">
      <header className="landing-nav">
        <a
          className="landing-brand"
          href="/"
          onClick={(event) => {
            event.preventDefault()
            onNavigate('/')
          }}
        >
          <BrandMark />
          <span>DeskAI</span>
        </a>
        <nav className="landing-nav-links" aria-label="Main navigation">
          <a href="#features">Platform</a>
          <a href="#how-it-works">How it works</a>
          <a href="#benefits">Why DeskAI</a>
        </nav>
        <div className="landing-nav-actions">
          <button type="button" className="landing-login-link" onClick={() => onNavigate('/login')}>
            Login
          </button>
          <button type="button" className="button button--primary button--nav" onClick={openRoleSelection}>
            Get started <span aria-hidden="true">↗</span>
          </button>
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero-glow landing-hero-glow--one" aria-hidden="true" />
          <div className="landing-hero-glow landing-hero-glow--two" aria-hidden="true" />
          <div className="landing-hero-copy">
            <p className="landing-eyebrow"><span /> AGENTIC AI SERVICE DESK</p>
            <h1>Support that thinks <span>ahead.</span></h1>
            <p className="landing-hero-description">
              Smart knowledge retrieval, intelligent incident management, AI-powered
              troubleshooting, ticket automation, and human escalation.
            </p>
            <div className="landing-hero-actions">
              <button type="button" className="button button--primary" onClick={openRoleSelection}>
                Get started <span aria-hidden="true">→</span>
              </button>
              <button type="button" className="button button--glass" onClick={() => onNavigate('/login')}>
                Login
              </button>
            </div>
            <div className="landing-social-proof">
              <div className="landing-avatar-stack" aria-hidden="true">
                <span>J</span><span>M</span><span>A</span><span>+</span>
              </div>
              <p><strong>One smarter service desk.</strong><br />Built for people and the teams who support them.</p>
            </div>
          </div>

          <div className="hero-product-wrap" aria-label="DeskAI support conversation preview">
            <div className="hero-orbit hero-orbit--outer" aria-hidden="true" />
            <div className="hero-orbit hero-orbit--inner" aria-hidden="true" />
            <div className="hero-product-card">
              <div className="hero-product-topbar">
                <div className="hero-window-dots"><i /><i /><i /></div>
                <span>DESKAI SUPPORT</span>
                <span className="hero-live-indicator"><i /> Live</span>
              </div>
              <div className="hero-chat-content">
                <div className="hero-preview-label">TODAY · 9:41 AM</div>
                <div className="hero-user-message">I can’t connect to the VPN this morning.</div>
                <div className="hero-ai-message">
                  <div className="hero-ai-avatar"><BrandMark /></div>
                  <div>
                    <strong>DeskAI Assistant <span>AI assistant</span></strong>
                    <p>Let’s get you connected. First, check that your network is active, then reopen the VPN client.</p>
                    <div className="hero-source-chip"><span>▤</span> Remote access guide <b>·</b> 3 steps</div>
                  </div>
                </div>
                <div className="hero-classification-card">
                  <div className="hero-classification-icon">◈</div>
                  <div><small>ISSUE CLASSIFIED</small><strong>Network access <span>High priority</span></strong></div>
                  <span className="hero-check">✓</span>
                </div>
                <div className="hero-prompt-bar"><span>Ask DeskAI anything...</span><b>↑</b></div>
              </div>
            </div>
            <div className="hero-floating-card hero-floating-card--top">
              <span className="hero-floating-icon">✦</span>
              <div><small>AI RESOLUTION</small><strong>Always on</strong></div>
              <span className="hero-floating-pulse" />
            </div>
            <div className="hero-floating-card hero-floating-card--bottom">
              <span className="hero-chart-icon">↗</span>
              <div><small>SMART ROUTING</small><strong>Right team, faster</strong></div>
            </div>
          </div>
          <div className="landing-hero-bottom" aria-hidden="true">
            <span>KNOWLEDGE</span><i /><span>INTELLIGENCE</span><i /><span>HUMAN CONNECTION</span>
          </div>
        </section>

        <section className="landing-section landing-features" id="features">
          <div className="section-heading">
            <p className="section-eyebrow">ONE PLATFORM, MORE MOMENTUM</p>
            <h2>Every support moment, <span>connected.</span></h2>
            <p>From the first question to the final resolution, DeskAI keeps support moving.</p>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <article className="feature-card" key={feature.title}>
                <span className={`feature-icon feature-icon--${feature.tone}`} aria-hidden="true">{feature.icon}</span>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
                <span className="feature-card-arrow" aria-hidden="true">↗</span>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section landing-how" id="how-it-works">
          <div className="section-heading section-heading--left">
            <p className="section-eyebrow">A BETTER WAY TO GET HELP</p>
            <h2>From question to <span>resolution.</span></h2>
            <p>One clear journey that brings knowledge, automation, and people together.</p>
          </div>
          <div className="steps-track">
            {steps.map(([number, title, description]) => (
              <article className="step-card" key={number}>
                <span className="step-number">{number}</span>
                <span className="step-marker" aria-hidden="true" />
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="benefits-section" id="benefits">
          <div className="benefits-intro">
            <p className="section-eyebrow section-eyebrow--light">BUILT FOR BETTER SERVICE</p>
            <h2>Give your people<br />their time back.</h2>
            <p>Less searching. Less friction. More meaningful support for everyone.</p>
            <button type="button" className="button button--light" onClick={openRoleSelection}>
              Explore DeskAI <span aria-hidden="true">→</span>
            </button>
          </div>
          <div className="benefits-grid">
            {benefits.map(([title, description], index) => (
              <article className="benefit-card" key={title}>
                <span className="benefit-number">0{index + 1}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <a className="landing-brand" href="/" onClick={(event) => { event.preventDefault(); onNavigate('/') }}>
          <BrandMark /><span>DeskAI</span>
        </a>
        <p>Agentic AI Service Desk</p>
        <span>© {new Date().getFullYear()} DeskAI. Support, made thoughtful.</span>
      </footer>

      {isRoleSelectionOpen && (
        <div
          className="role-selection-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setIsRoleSelectionOpen(false)
          }}
        >
          <section
            className="role-selection-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="role-selection-title"
            aria-describedby="role-selection-description"
          >
            <button
              className="role-selection-close"
              type="button"
              aria-label="Close role selection"
              onClick={() => setIsRoleSelectionOpen(false)}
            >
              ×
            </button>
            <span className="role-selection-mark"><BrandMark /></span>
            <p className="section-eyebrow">WELCOME TO DESKAI</p>
            <h2 id="role-selection-title">Welcome to DeskAI</h2>
            <p id="role-selection-description">Choose how you would like to continue.</p>
            <div className="role-selection-options">
              <button
                className="role-selection-card role-selection-card--assistant"
                type="button"
                onClick={() => onNavigate('/assistant')}
              >
                <span className="role-selection-card-icon" aria-hidden="true">✦</span>
                <span className="role-selection-card-copy">
                  <strong>Talk to AI Assistant</strong>
                  <span>Get instant support, troubleshooting assistance, knowledge search, and ticket creation.</span>
                </span>
                <span className="role-selection-card-action">Start Chatting <span aria-hidden="true">→</span></span>
              </button>
              <button
                className="role-selection-card role-selection-card--admin"
                type="button"
                onClick={() => onNavigate('/admin')}
              >
                <span className="role-selection-card-icon" aria-hidden="true">▤</span>
                <span className="role-selection-card-copy">
                  <strong>Admin Portal</strong>
                  <span>Manage tickets, knowledge base, analytics, and human support operations.</span>
                </span>
                <span className="role-selection-card-action">Open Admin Portal <span aria-hidden="true">→</span></span>
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
