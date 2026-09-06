import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { TrainFront, LogOut, ShieldCheck, Radio, Users } from 'lucide-react'

interface LayoutProps {
  children: React.ReactNode
  title: string
  subtitle?: string
}

export default function Layout({ children, title, subtitle }: LayoutProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/engineer', label: 'Engineer', icon: Users, roles: ['engineer'] },
    { to: '/officer', label: 'Officer', icon: ShieldCheck, roles: ['officer'] },
    { to: '/live', label: 'Live Ops', icon: Radio, roles: ['engineer', 'officer'] },
  ]

  return (
    <div className="min-h-screen rail-canvas">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0B1F3A]">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="relative w-9 h-9 rounded-xl bg-white/10 border border-white/15 flex items-center justify-center">
                <TrainFront className="w-5 h-5 text-white" />
                <span className="absolute inset-0 rounded-xl bg-blue-400/20 animate-pulse" />
              </div>
              <div>
                <h1 className="text-base font-extrabold tracking-tight">
                  <span className="text-white">RailSync</span>{' '}
                  <span className="text-white">AI</span>
                </h1>
                <p className="text-[11px] text-blue-200 -mt-0.5">{subtitle || (user?.role === 'officer' ? 'Officer Control Portal' : 'Engineer Portal')}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-4">
              <nav className="hidden md:flex items-center gap-1 bg-white/10 border border-white/10 rounded-xl p-1">
                {navItems
                  .filter(n => n.roles.includes(user?.role || ''))
                  .map(n => (
                    <Link
                      key={n.to}
                      to={n.to}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        location.pathname === n.to
                          ? 'bg-blue-400/25 text-white border border-blue-400/40'
                          : 'text-blue-200 hover:text-white'
                      }`}
                    >
                      <n.icon className="w-3.5 h-3.5" />
                      {n.label}
                    </Link>
                  ))}
              </nav>

              <div className="flex items-center gap-2.5">
                <div className="text-right leading-tight hidden sm:block">
                  <p className="text-xs font-semibold text-white">{user?.name}</p>
                  <p className="text-[10px] uppercase tracking-wide text-blue-200">{user?.role}</p>
                </div>
                <span className={`chip ${user?.role === 'officer' ? 'bg-white/15 text-white border-white/30' : 'bg-white/15 text-white border-white/30'}`}>
                  {user?.role}
                </span>
                <button
                  onClick={handleLogout}
                  className="p-2 rounded-lg text-blue-200 hover:text-red-300 hover:bg-red-400/20 transition-colors"
                  title="Logout"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>
      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>
    </div>
  )
}