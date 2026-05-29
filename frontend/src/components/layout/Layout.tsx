import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { NotificationBar } from "./NotificationBar";

export function Layout() {
  return (
    <div className="flex h-screen bg-ac-surface">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <NotificationBar />
        <div className="flex-1 overflow-y-auto">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
