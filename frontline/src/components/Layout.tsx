import { Link, useLocation } from "react-router-dom";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>GuardianBaby</h1>
          <p>Frontend Monitoring Console</p>
        </div>
        <nav className="nav-links">
          <Link className={location.pathname.includes("dashboard") ? "active" : ""} to="/dashboard">
            Dashboard
          </Link>
          <Link className={location.pathname.includes("history") ? "active" : ""} to="/history">
            History & Analytics
          </Link>
        </nav>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}
