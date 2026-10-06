import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { ReactNode, useEffect } from "react";
import clsx from "clsx";
import { useAuthStore } from "@/store/authStore";
import { usePrefsStore } from "@/store/prefsStore";
import { reviewApi } from "@/api";
import { useState } from "react";

const navItems = [
  { path: "/characters", label: "角色设计" },
  { path: "/scripts", label: "脚本场次" },
  { path: "/reviews", label: "待复核" },
  { path: "/images", label: "参考图库" },
];

const roleLabel: Record<string, string> = {
  admin: "管理员",
  editor: "编剧",
  viewer: "观众",
};

const Layout = ({ children }: { children: ReactNode }) => {
  const { user, hydrated, hydrate, logout } = useAuthStore();
  const { motionEnabled, toggleMotion } = usePrefsStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [openCount, setOpenCount] = useState<number | null>(null);
  const navItemsVisible = user?.role === "admin"
    ? [...navItems, { path: "/admin", label: "清理" }]
    : navItems;

  useEffect(() => {
    hydrate();
  }, [hydrate, location.pathname]);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    const load = () =>
      reviewApi
        .list("open")
        .then((items) => alive && setOpenCount(items.length))
        .catch(() => undefined);
    load();
    const timer = setInterval(load, 8000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [user, location.pathname]);

  if (!hydrated) return null;
  if (!user) {
    navigate("/login", { replace: true });
    return null;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link to="/characters" className="flex items-center gap-2.5">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent text-base font-bold text-white shadow-card">
              角
            </span>
            <div>
              <p className="text-[11px] text-slate-400">Character Workbench</p>
              <h1 className="text-base font-semibold leading-tight text-slate-900">
                角色设计工作台
              </h1>
            </div>
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {navItemsVisible.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  clsx(
                    "relative rounded-full px-3.5 py-2 text-sm font-medium transition",
                    isActive ? "bg-primary/10 text-primary" : "text-slate-600 hover:bg-slate-100",
                  )
                }
              >
                {item.label}
                {item.path === "/reviews" && openCount ? (
                  <span className="ml-1.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                    {openCount > 99 ? "99+" : openCount}
                  </span>
                ) : null}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleMotion}
              title={motionEnabled ? "动态效果：开（点击关闭）" : "动态效果：关"}
              className={clsx(
                "hidden h-9 w-9 items-center justify-center rounded-full ring-1 transition sm:inline-flex",
                motionEnabled
                  ? "bg-primary/5 text-primary ring-primary/30"
                  : "bg-slate-50 text-slate-400 ring-slate-200",
              )}
            >
              {motionEnabled ? "✨" : "⏸"}
            </button>
            <div className="hidden text-right sm:block">
              <p className="text-xs font-semibold text-slate-700">{user.display_name}</p>
              <p className="text-[11px] text-slate-400">{roleLabel[user.role] ?? user.role}</p>
            </div>
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="rounded-full px-3 py-1.5 text-xs font-medium text-slate-500 ring-1 ring-slate-200 transition hover:bg-slate-100"
            >
              退出
            </button>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
          {navItemsVisible.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                clsx(
                  "whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition",
                  isActive ? "bg-primary/10 text-primary" : "text-slate-600",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
      <footer className="border-t border-slate-200 bg-white/70 py-4">
        <p className="text-center text-xs text-slate-400">
          角色版本 · 引用依赖 · 异步封面 · 退役审计 · 服务端鉴权
        </p>
      </footer>
    </div>
  );
};

export default Layout;
