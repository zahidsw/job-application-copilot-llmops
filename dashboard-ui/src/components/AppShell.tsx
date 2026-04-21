import { NavLink, Outlet } from 'react-router-dom'
import { serviceLinks } from '../lib/format'

const navigation = [
  { to: '/', label: 'Overview', hint: 'live stack and recent runs' },
  { to: '/submit', label: 'Launch Run', hint: 'URL-first or manual application intake' },
  { to: '/profile', label: 'Profile Vault', hint: 'profile, uploads, and sample reuse' },
]

export function AppShell() {
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
        </header>
        <main className="workspace-body">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
