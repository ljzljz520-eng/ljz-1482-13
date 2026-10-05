import { useEffect, useRef } from "react";

/** 在 active=true 时按 interval 轮询，页面隐藏时自动暂停。 */
export function usePolling(fn: () => void, intervalMs: number, active = true) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    if (!active) return;
    let timer: number | undefined;
    const tick = async () => {
      if (document.visibilityState === "visible") {
        try {
          await saved.current();
        } catch {
          /* 错误提示由拦截器处理 */
        }
      }
      timer = window.setTimeout(tick, intervalMs);
    };
    timer = window.setTimeout(tick, intervalMs);
    return () => window.clearTimeout(timer);
  }, [intervalMs, active]);
}
