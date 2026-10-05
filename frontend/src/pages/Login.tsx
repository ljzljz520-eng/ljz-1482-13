import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { login } from "../api/endpoints";
import { useAuth } from "../store/auth";
import { Button, Field, inputCls } from "../components/ui";

const demoAccounts = [
  { username: "admin", password: "123456", desc: "管理员：可退役角色 / 物理清理图片" },
  { username: "editor_a", password: "123456", desc: "编剧：脚本、引用模式、台词批准" },
  { username: "editor_b", password: "123456", desc: "美术：角色版本、参考图、封面任务" },
  { username: "viewer", password: "123456", desc: "访客：只读" },
];

export default function Login() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123456");
  const [loading, setLoading] = useState(false);
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await login(username.trim(), password);
      localStorage.setItem("cs_token", res.access_token);
      setUser(res.user);
      toast.success(`欢迎，${res.user.display_name}`);
      navigate(from, { replace: true });
    } catch (err) {
      toast.error((err as { friendlyMessage?: string }).friendlyMessage ?? "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[80vh] items-center justify-center">
      <div className="grid w-full max-w-4xl gap-6 md:grid-cols-2">
        <div className="hidden flex-col justify-center rounded-3xl bg-gradient-to-br from-blue-600 via-indigo-600 to-violet-600 p-8 text-white md:flex">
          <h2 className="text-2xl font-bold">版本与依赖管理</h2>
          <p className="mt-3 text-sm leading-7 text-white/85">
            人物外观、语气、参考图与限制词全部按不可变版本保存。脚本可固定某版或跟随最新，
            两种引用在场次页清晰可见；已批准台词不会因角色改版而被悄悄重释。
          </p>
          <ul className="mt-6 space-y-2 text-sm text-white/90">
            <li>🔒 修改角色只追加新版本（乐观锁 + 行级锁）</li>
            <li>🔁 退役先查真实反向引用，支持替换后退役</li>
            <li>🖼️ 封面任务绑定原图与裁切参数，旧任务晚到不覆盖</li>
            <li>🧹 清理图片时保留历史导出仍引用的对象</li>
          </ul>
        </div>

        <form onSubmit={submit} className="rounded-3xl border border-slate-200 bg-white p-8 shadow-card">
          <h3 className="text-lg font-semibold text-slate-900">登录角色工作室</h3>
          <p className="mt-1 text-sm text-slate-500">权限在服务端强制校验</p>
          <div className="mt-6 space-y-4">
            <Field label="用户名">
              <input className={inputCls} value={username} onChange={(e) => setUsername(e.target.value)} />
            </Field>
            <Field label="密码">
              <input
                type="password"
                className={inputCls}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Button type="submit" loading={loading} className="w-full">
              登 录
            </Button>
          </div>
          <div className="mt-6 space-y-2">
            <p className="text-xs font-medium text-slate-400">演示账号（点击填充）</p>
            {demoAccounts.map((a) => (
              <button
                type="button"
                key={a.username}
                onClick={() => {
                  setUsername(a.username);
                  setPassword(a.password);
                }}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-left text-xs text-slate-600 transition hover:border-blue-300 hover:bg-blue-50/40"
              >
                <span className="font-mono font-semibold text-slate-800">
                  {a.username} / {a.password}
                </span>
                <span className="ml-2 text-slate-400">{a.desc}</span>
              </button>
            ))}
          </div>
        </form>
      </div>
    </div>
  );
}
