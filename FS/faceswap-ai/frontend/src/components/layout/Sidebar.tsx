import { Link, useLocation } from 'react-router-dom'
import {
  Home,
  PlusCircle,
  FolderOpen,
  Settings,
  Zap,
} from 'lucide-react'
import { cn } from '@/utils/cn'

const navItems = [
  { href: '/', icon: Home, label: 'Inicio' },
  { href: '/project/new', icon: PlusCircle, label: 'Nuevo proyecto' },
  { href: '/projects', icon: FolderOpen, label: 'Mis proyectos' },
  { href: '/settings', icon: Settings, label: 'Configuración' },
]

export function Sidebar() {
  const location = useLocation()

  return (
    <aside className="fixed left-0 top-0 h-full w-16 md:w-56 z-40 flex flex-col bg-card border-r border-border">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-border">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-purple-500/20">
          <Zap className="h-5 w-5 text-white" />
        </div>
        <span className="hidden md:block font-bold text-base text-gradient">
          FaceSwap AI
        </span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 p-2 flex-1 mt-2">
        {navItems.map(({ href, icon: Icon, label }) => {
          const active =
            href === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(href)
          return (
            <Link
              key={href}
              to={href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all',
                active
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-accent hover:text-foreground'
              )}
            >
              <Icon
                className={cn(
                  'h-5 w-5 shrink-0',
                  active ? 'text-primary' : 'text-muted-foreground'
                )}
              />
              <span className="hidden md:block">{label}</span>
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="hidden md:block p-4 border-t border-border">
        <p className="text-[10px] text-muted-foreground leading-relaxed">
          Solo para uso con consentimiento explícito.
          <br />
          Prohibido suplantar identidades.
        </p>
      </div>
    </aside>
  )
}
