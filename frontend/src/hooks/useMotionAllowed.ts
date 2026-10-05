import { useEffect, useState } from "react";

/**
 * 动效守门：同时满足两项才允许播放动画
 *  1) 元素/页面处于可见状态（IntersectionObserver / document.visibilityState）
 *  2) 用户未开启“减少动态效果”（prefers-reduced-motion）且未在设置中关闭动效
 */
export function useMotionAllowed<T extends Element>(
  ref: React.RefObject<T>,
  options?: { userPreference?: boolean }
): boolean {
  const userPreference = options?.userPreference ?? true;
  const [inView, setInView] = useState(false);
  const [pageVisible, setPageVisible] = useState(!document.hidden);
  const [reduced, setReduced] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => setInView(entries.some((e) => e.isIntersecting)),
      { threshold: 0.2 }
    );
    io.observe(el);
    const onVis = () => setPageVisible(!document.hidden);
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMq = (e: MediaQueryListEvent) => setReduced(e.matches);
    document.addEventListener("visibilitychange", onVis);
    mq.addEventListener("change", onMq);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      mq.removeEventListener("change", onMq);
    };
  }, [ref]);

  return inView && pageVisible && !reduced && userPreference;
}
