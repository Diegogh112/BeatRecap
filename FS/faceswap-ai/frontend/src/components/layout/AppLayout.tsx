import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Toaster } from './Toaster'

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      {/* Main content — offset por el sidebar */}
      <main className="ml-16 md:ml-56 min-h-screen">
        <div className="max-w-7xl mx-auto p-4 md:p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
      <Toaster />
    </div>
  )
}
