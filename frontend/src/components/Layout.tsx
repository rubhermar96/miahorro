import { Outlet } from 'react-router'

import { BottomNav } from './BottomNav'
import { OfflineStatus } from './OfflineStatus'
import { UpdatePrompt } from './UpdatePrompt'

export function Layout() {
  return (
    <div className="app">
      <main className="content">
        <OfflineStatus />
        <Outlet />
      </main>
      <UpdatePrompt />
      <BottomNav />
    </div>
  )
}
