import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { NotificationBar } from "./NotificationBar";

export function Layout() {
  return (
    <div className="flex h-screen bg-ac-surface">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Radial gradient: subtle warmth in the content area top-right */}
        <div
          className="pointer-events-none absolute top-0 right-0 w-[600px] h-[400px] opacity-30 dark:opacity-[0.12]"
          style={{
            background: "radial-gradient(ellipse at top right, var(--ac-primary-bg) 0%, transparent 70%)",
          }}
          aria-hidden
        />
        <NotificationBar />
        <div className="flex-1 overflow-y-auto relative z-10">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
