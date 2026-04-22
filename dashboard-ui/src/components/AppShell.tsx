import { NavLink, Outlet } from 'react-router-dom'
import { triggerLogout } from '../lib/auth'
import { serviceLinks } from '../lib/format'
import { appRuntimeConfig } from '../lib/runtimeConfig'

const navigation = [
  { to: '/', label: 'Overview', hint: 'live stack and recent runs' },
  { to: '/submit', label: 'Launch Run', hint: 'URL-first or manual application intake' },
  { to: '/profile', label: 'Profile Vault', hint: 'profile, uploads, and sample reuse' },
]

export function AppShell() {
  const isProtectedByEntra = appRuntimeConfig.entraAuthEnabled

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">JC</div>
          <div>
            <p className="eyebrow">Job Application Copilot</p>
            <h1 className="brand-title">Operator deck for application runs.</h1>
          </div>
        </div>

        <nav className="nav-stack" aria-label="Primary">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}
            >
              <span>{item.label}</span>
              <small>{item.hint}</small>
            </NavLink>
          ))}
        </nav>

        <section className="sidebar-section">
          <p className="eyebrow">Observability</p>
          <div className="link-stack">
            {serviceLinks().map((link) => (
              <a key={link.label} className="service-link" href={link.href} target="_blank" rel="noreferrer">
                <span>{link.label}</span>
                <small>{link.note}</small>
              </a>
            ))}
          </div>
        </section>

        <section className="sidebar-section subtle-copy">
          <p className="eyebrow">Policy</p>
          <p>Every run can prepare documents, but no dispatch happens until an operator approves it.</p>
        </section>
      </aside>

      <div className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Recruiting operations</p>
            <h2 className="workspace-title">Local-first dashboard for runs, vault assets, and approval flow.</h2>
          </div>
          {isProtectedByEntra ? (
            <div className="workspace-actions">
              <button type="button" className="ghost-button session-action-button" onClick={() => triggerLogout()}>
                Sign out
              </button>
              <p className="session-hint">Ends the current session so the next sign-in lets you choose an email again.</p>
            </div>
          ) : null}
        </header>
        <main className="workspace-body">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
