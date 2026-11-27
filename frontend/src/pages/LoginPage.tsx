import type { AppRoute } from '../types/navigation'

interface LoginPageProps {
  onNavigate: (destination: AppRoute) => void
}

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

export function LoginPage({ onNavigate }: LoginPageProps) {
  return (
    <main className="login-page">
      <section className="login-story">
        <a className="landing-brand login-brand" href="/" onClick={(event) => { event.preventDefault(); onNavigate('/') }}>
          <BrandMark /><span>DeskAI</span>
        </a>
        <div className="login-story-copy">
          <p className="landing-eyebrow"><span /> AGENTIC AI SERVICE DESK</p>
          <h1>Great support starts with a better conversation.</h1>
          <p>One workspace for helpful answers, smarter service, and human connection.</p>
          <div className="login-story-orbit" aria-hidden="true">
            <div className="login-orbit-center"><BrandMark /></div>
            <span className="login-orbit-node login-orbit-node--one">✦</span>
            <span className="login-orbit-node login-orbit-node--two">◎</span>
            <span className="login-orbit-node login-orbit-node--three">↗</span>
          </div>
        </div>
        <p className="login-story-footer">Thoughtful support, powered by DeskAI.</p>
      </section>
      <section className="login-form-side">
        <button type="button" className="login-back-link" onClick={() => onNavigate('/')}>
          <span aria-hidden="true">←</span> Back to DeskAI
        </button>
        <div className="login-card">
          <div className="login-card-mark"><BrandMark /></div>
          <p className="section-eyebrow">WELCOME TO DESKAI</p>
          <h2>Sign in to your workspace</h2>
          <p className="login-card-copy">Authentication is not enabled in this demo. Continue to explore the application.</p>
          <label className="login-label" htmlFor="demo-email">Work email</label>
          <input id="demo-email" className="login-input" type="email" placeholder="you@company.com" autoComplete="email" />
          <button type="button" className="button button--primary login-submit" onClick={() => onNavigate('/assistant')}>
            Continue to DeskAI <span aria-hidden="true">→</span>
          </button>
          <div className="login-demo-note"><span>✦</span> Demo access · No password required</div>
          <p className="login-terms">By continuing, you’re entering a product demo. No account or personal data is submitted.</p>
        </div>
        <p className="login-form-footer">Need a hand? <button type="button" onClick={() => onNavigate('/assistant')}>Explore the support workspace</button></p>
      </section>
    </main>
  )
}
