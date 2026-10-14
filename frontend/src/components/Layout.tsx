import { Outlet } from 'react-router'

import { BottomNav } from './BottomNav'
import { UpdatePrompt } from './UpdatePrompt'

export function Layout() {
  return (
    <div className="app">
      <main className="content">
        <Outlet />
      </main>
      <UpdatePrompt />
      <BottomNav />
    </div>
  )
}
