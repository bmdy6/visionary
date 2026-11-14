import { NavLink } from "react-router-dom";
import { Sparkles, Images, User } from "lucide-react";
import useBilling, { trialBadge } from "../hooks/useBilling";
import { usePWA } from "../hooks/usePWA";

export default function Layout({ children }) {
  const { user } = useBilling();
  const pwa = usePWA();
  return (
    <div className="site-layout">
      <header className="site-header">
        <div className="header-inner">
          <NavLink to="/" className="brand">
            Visionary
          </NavLink>
          <nav className="desktop-nav" aria-label="主导航">
            <NavLink to="/">创作</NavLink>
            <NavLink to="/history">我的作品</NavLink>
            {user?.is_admin && <NavLink to="/admin">管理后台</NavLink>}
          </nav>
          <div className="header-account">
            {pwa.isInstallable && !pwa.isInstalled && (
              <button onClick={pwa.promptInstall}>安装到桌面</button>
            )}
            <NavLink
              to="/profile"
              className="credits-badge"
              data-testid="credits-badge"
            >
              {trialBadge(user)}
            </NavLink>
            <NavLink to="/profile" className="desktop-user">
              <span className="avatar">
                <User size={20} />
              </span>
              {user?.username || "账户"}
            </NavLink>
          </div>
        </div>
      </header>
      <main className="site-main">{children}</main>
      <nav className="mobile-nav" aria-label="底部导航">
        {[
          ["/", "创作", Sparkles],
          ["/history", "作品", Images],
          ["/profile", "我的", User],
        ].map(([to, label, Icon]) => (
          <NavLink key={to} to={to}>
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
