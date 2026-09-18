import type { ReactNode } from "react";

type NavIconName = "home" | "activity" | "analysis" | "sessions" | "students" | "users" | "manage";

export function NavIcon({ name }: { name: NavIconName }) {
  const paths: Record<NavIconName, ReactNode> = {
    home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" /><path d="M9 21v-7h6v7" /></>,
    activity: <><path d="M3 12h4l2-4 4 8 2-4h6" /><path d="M12 3a9 9 0 1 0 9 9" /></>,
    analysis: <><rect x="3" y="6" width="18" height="14" rx="2" /><circle cx="12" cy="13" r="3" /><path d="M8 6 9 4h6l1 2" /></>,
    sessions: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    students: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 6 0 0 1 12 0v2" /><path d="M17 5a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 5v1" /></>,
    users: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
    manage: <><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="9" cy="6" r="2" fill="currentColor" stroke="none" /><circle cx="15" cy="12" r="2" fill="currentColor" stroke="none" /><circle cx="10" cy="18" r="2" fill="currentColor" stroke="none" /></>,
  };
  return <svg className="nav-icon" aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

export type { NavIconName };
