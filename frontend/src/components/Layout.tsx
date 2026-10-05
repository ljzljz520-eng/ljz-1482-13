import { ReactNode, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useAuth } from "../store/auth";

const navItems = [
  { path: "/", label: "角色设计", icon: "🎭" },
  { path: "/scripts", label: "脚本场次", icon: "📜" },
  { path: "/review", label: "复核工作台", icon: "🛡️" },
  { path: "/assets", label: "图片与清理", icon: "🖼️" },
  { path: "/exports", label: "导出快照", icon: "📦" },
];

const roleLabel: Record<string, string> = {
  admin: "管理员",
  editor: "编辑",
  viewer: "访客",
};

const Layout = ({ children }: { children: ReactNode }) => {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-base font-bold text-white shadow-card">
              角
            </span>
            <div>
              <p className="text-xs text-slate-400">Character Studio</p>
              <h1 className="text-base font-semibold leading-tight text-slate-900">
                角色工作室
              </h1>
            </div>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                className={({ isActive }) =>
                  clsx(
                    "rounded-full px-3.5 py-2 text-sm font-medium transition",
                    isActive
                      ? "bg-blue-50 text-blue-700"
                      : "text-slate-600 hover:bg-slate-100"
                  )
                }
              >
                <span className="mr-1">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            {user ? (
              <div className="hidden items-center gap-2 sm:flex">
                <div className="text-right">
                  <p className="text-sm font-medium leading-tight text-slate-800">
                    {user.display_name}
                  </p>
                  <p className="text-xs text-slate-400">{roleLabel[user.role]}</p>
                </div>
                <button
                  onClick={() => {
                    logout();
                    navigate("/login");
                  }}
                  className="rounded-lg px-2.5 py-1.5 text-sm text-slate-500 transition hover:bg-slate-100"
                >
                  退出
                </button>
              </div>
            ) : (
              <Link
                to="/login"
                state={{ from: location.pathname }}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-700"
              >
                登录
              </Link>
            )}
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 transition hover:border-blue-400 hover:text-blue-600 md:hidden"
              aria-label="切换菜单"
            >
              <span className="relative block h-0.5 w-5 bg-current">
                <span className="absolute -top-1.5 block h-0.5 w-5 bg-current" />
                <span className="absolute top-1.5 block h-0.5 w-5 bg-current" />
              </span>
            </button>
          </div>
        </div>

        {menuOpen && (
          <div className="border-t border-slate-200 bg-white/95 md:hidden">
            <div className="mx-auto grid max-w-7xl grid-cols-2 gap-2 px-4 py-3">
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "/"}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    clsx(
                      "rounded-xl px-3 py-2 text-sm font-medium transition",
                      isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100"
                    )
                  }
                >
                  <span className="mr-1">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        )}
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>

      <footer className="border-t border-slate-200 bg-white/70">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-4 py-5 text-xs text-slate-400 sm:flex-row">
          <span>角色工作室 · 不可变版本 / 显式引用 / 安全退役</span>
          <span>权限完全由服务端校验 · {new Date().getFullYear()}</span>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
