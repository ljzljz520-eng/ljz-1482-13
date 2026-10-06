import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { authApi } from "@/api";
import { useAuthStore } from "@/store/authStore";
import { Button, Field, Input } from "@/components/ui";

const demoAccounts = [
  { username: "admin", password: "123456", label: "管理员", desc: "退役 / 撤销授权 / 清理" },
  { username: "editor", password: "123456", label: "编剧", desc: "编辑角色、台词与任务" },
  { username: "viewer", password: "123456", label: "观众", desc: "只读浏览全部内容" },
];

const LoginPage = () => {
  const navigate = useNavigate();
  const setSession = useAuthStore((s) => s.setSession);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123456");
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await authApi.login(username.trim(), password);
      setSession(data.user, data.token);
      toast.success(`欢迎回来，${data.user.display_name}`);
      navigate("/characters");
    } catch {
      /* interceptor already toasted */
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at 18% 20%, rgba(22,93,255,0.14), transparent 40%), radial-gradient(circle at 82% 10%, rgba(255,125,0,0.14), transparent 38%)",
        }}
      />
      <div className="relative grid w-full max-w-4xl gap-6 md:grid-cols-[1.1fr_1fr]">
        <div className="hidden flex-col justify-between rounded-3xl bg-gradient-to-br from-primary to-indigo-700 p-8 text-white shadow-card md:flex">
          <div>
            <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15 text-xl">
              🎬
            </div>
            <h2 className="text-2xl font-bold leading-snug">
              角色设计版本
              <br />& 依赖管理工作台
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-white/80">
              维护人物外观、语气、参考图与限制词；脚本可固定旧版或跟随最新版，
              已批准台词的解释永远不会被悄悄改写。
            </p>
          </div>
          <ul className="space-y-2 text-sm text-white/85">
            <li>🔒 乐观锁并发编辑 · 引用退役审计</li>
            <li>🖼 封面任务绑定原图与裁切参数</li>
            <li>🧾 授权撤销级联 · 历史导出保护</li>
          </ul>
        </div>
        <form
          onSubmit={submit}
          className="rounded-3xl bg-white p-8 shadow-card ring-1 ring-slate-100"
        >
          <h1 className="text-xl font-bold text-slate-900">登录工作台</h1>
          <p className="mt-1 text-xs text-slate-400">所有写操作均在服务端二次鉴权</p>
          <div className="mt-6 space-y-4">
            <Field label="用户名">
              <Input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
            </Field>
            <Field label="密码">
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Button type="submit" loading={loading} className="w-full">
              登录
            </Button>
          </div>
          <div className="mt-6 border-t border-slate-100 pt-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              演示账号（点击填充）
            </p>
            <div className="grid gap-2">
              {demoAccounts.map((acc) => (
                <button
                  type="button"
                  key={acc.username}
                  onClick={() => {
                    setUsername(acc.username);
                    setPassword(acc.password);
                  }}
                  className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-left ring-1 ring-slate-100 transition hover:bg-primary/5 hover:ring-primary/30"
                >
                  <span className="text-sm font-medium text-slate-700">{acc.label}</span>
                  <span className="text-[11px] text-slate-400">{acc.desc}</span>
                </button>
              ))}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
