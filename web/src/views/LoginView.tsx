import { useEffect, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { LoginGlobe } from '../components/LoginGlobe'
import { useAuth } from '../auth'

const DEMOS = [
  { label: 'Compliance Analyst', username: 'analyst', password: 'change-me-analyst' },
  { label: 'FIU Team Lead', username: 'fiu_lead', password: 'change-me-fiu' },
  { label: 'MRM Auditor', username: 'mrm_auditor', password: 'change-me-mrm' },
]

export function LoginView() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [reduced, setReduced] = useState(false)
  const heroRef = useRef<HTMLElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const spotRef = useRef<HTMLDivElement>(null)
  const target = useRef({ x: 0, y: 0, sx: 50, sy: 40 })
  const current = useRef({ x: 0, y: 0, sx: 50, sy: 40 })
  const rafRef = useRef(0)

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => {
      mq.removeEventListener('change', onChange)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [])

  function kickMotion() {
    if (reduced || rafRef.current) return
    const step = () => {
      const c = current.current
      const t = target.current
      c.x += (t.x - c.x) * 0.12
      c.y += (t.y - c.y) * 0.12
      c.sx += (t.sx - c.sx) * 0.18
      c.sy += (t.sy - c.sy) * 0.18
      if (stageRef.current) {
        stageRef.current.style.transform = `translate3d(${c.x.toFixed(1)}px, ${c.y.toFixed(1)}px, 0) scale(1.04)`
      }
      if (spotRef.current) {
        spotRef.current.style.setProperty('--sx', `${c.sx.toFixed(1)}%`)
        spotRef.current.style.setProperty('--sy', `${c.sy.toFixed(1)}%`)
      }
      if (
        Math.abs(t.x - c.x) > 0.08 ||
        Math.abs(t.y - c.y) > 0.08 ||
        Math.abs(t.sx - c.sx) > 0.05 ||
        Math.abs(t.sy - c.sy) > 0.05
      ) {
        rafRef.current = requestAnimationFrame(step)
      } else {
        rafRef.current = 0
      }
    }
    rafRef.current = requestAnimationFrame(step)
  }

  function onHeroPointerMove(e: ReactPointerEvent<HTMLElement>) {
    if (reduced) return
    const hero = heroRef.current
    if (!hero) return
    const r = hero.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    target.current = {
      x: (px - 0.5) * 56,
      y: (py - 0.5) * 36,
      sx: px * 100,
      sy: py * 100,
    }
    kickMotion()
  }

  function onHeroPointerLeave() {
    if (reduced) return
    target.current = { x: 0, y: 0, sx: 70, sy: 55 }
    kickMotion()
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(username.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`login-mask${reduced ? ' reduce-motion' : ''}`}>
      <section
        className="login-hero"
        ref={heroRef}
        onPointerMove={onHeroPointerMove}
        onPointerLeave={onHeroPointerLeave}
      >
        <div className="login-hero-scroll">
          <div className="login-hero-screen">
            <div className="login-spotlight" ref={spotRef} />
            <div className="login-scanline" />
            <div className="login-hero-inner">
            <div className="login-hero-bar">
              <div className="login-brand">
                <svg className="login-mark" viewBox="0 0 48 48" fill="none" aria-hidden="true">
                  <path
                    d="M24 4l16 6v12c0 11.2-7.2 21.4-16 24-8.8-2.6-16-12.8-16-24V10l16-6z"
                    stroke="#60A5FA"
                    strokeWidth="2.2"
                    fill="rgba(37,99,235,.12)"
                  />
                  <circle cx="24" cy="22" r="7" stroke="#93C5FD" strokeWidth="2" />
                  <circle cx="24" cy="22" r="2.4" fill="#93C5FD" />
                </svg>
                <div className="login-brand-name">CORRIDOR WATCH</div>
              </div>
              <div className="login-live">
                <i /> Live corridor graph
              </div>
            </div>
            <div className="login-globe-stage" ref={stageRef}>
              <LoginGlobe reduced={reduced} />
            </div>
            </div>
          </div>
          <div className="login-story">
            <div className="login-sheet">
              <div className="login-block">
                <p className="login-kicker">See a case</p>
                <h3>Middle Bank, in twenty seconds</h3>
                <div className="login-film">
                  <video className="login-demo" controls playsInline preload="metadata" src="/static/login-demo.mp4">
                    Your browser cannot play this video.
                  </video>
                  <p>Queue, the unnamed hop, the evidence, then the verdict.</p>
                </div>
              </div>
              <div className="login-block">
                <p className="login-kicker">Who signs in</p>
                <h3>Three desks, one case</h3>
                <div className="login-cards">
                  <article>
                    <p className="login-kicker">Analyst</p>
                    <b>Work the queue</b>
                    <span>Open the corridor, follow the graph, and read the evidence on the verdict.</span>
                  </article>
                  <article>
                    <p className="login-kicker">FIU lead</p>
                    <b>Decide and file</b>
                    <span>Record the decision and the note, then a SAR for FinCEN, MAS, or AUSTRAC.</span>
                  </article>
                  <article>
                    <p className="login-kicker">MRM auditor</p>
                    <b>See the model</b>
                    <span>Mined rules and the model record stay in this console.</span>
                  </article>
                </div>
              </div>
              <div className="login-block">
                <p className="login-kicker">On a case</p>
                <h3>What happens in a case</h3>
                <div className="login-flow">
                  <div className="login-flow-rail" aria-hidden="true">
                    <i>
                      <b />
                    </i>
                  </div>
                  <ol>
                    <li>
                      <em>1</em>
                      <b>Queue</b>
                      <span>Open the case</span>
                    </li>
                    <li>
                      <em>2</em>
                      <b>Graph</b>
                      <span>Follow the hop</span>
                    </li>
                    <li>
                      <em>3</em>
                      <b>Evidence</b>
                      <span>Read the citations</span>
                    </li>
                    <li>
                      <em>4</em>
                      <b>File</b>
                      <span>Decide and export</span>
                    </li>
                  </ol>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <form
          className="login-card login-rise"
          style={{ animationDelay: '220ms' }}
          onSubmit={(e) => void submit(e)}
        >
          <div className="login-card-logo">
            <div className="nm">CORRIDOR WATCH</div>
          </div>
          <h2>Sign in</h2>
          <p className="sub">Analyst and FIU lead console access</p>
          {error && <p className="error">{error}</p>}
          <div className="field">
            <label htmlFor="user">Username</label>
            <input
              id="user"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="Enter your analyst ID"
            />
          </div>
          <div className="field">
            <label htmlFor="pass">Password</label>
            <input
              id="pass"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
            />
          </div>
          <div className="login-or">OR DEMO</div>
          <div className="demo-roles">
            {DEMOS.map((d) => (
              <button
                key={d.username}
                type="button"
                className="btn secondary login-press"
                onClick={() => {
                  setUsername(d.username)
                  setPassword(d.password)
                }}
              >
                {d.label}
              </button>
            ))}
          </div>
          <button className="btn login-submit login-press" type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign In →'}
          </button>
          <div className="login-secure">Secure · Encrypted · Compliant</div>
        </form>
      </section>
    </div>
  )
}
