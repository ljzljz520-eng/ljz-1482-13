import { useMemo } from "react";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";
import { usePrefsStore } from "@/store/prefsStore";
import { useInView } from "./useInView";
import { useDocumentVisible } from "./useDocumentVisible";

/**
 * Animation gate combining three conditions:
 *  1. the element is inside the viewport;
 *  2. the browser tab is visible;
 *  3. motion is allowed by BOTH the user's in-app preference and the OS
 *     "prefers-reduced-motion" setting.
 */
export function useShouldAnimate<T extends HTMLElement = HTMLDivElement>() {
  const { ref, inView } = useInView<T>();
  const tabVisible = useDocumentVisible();
  const osReduced = usePrefersReducedMotion();
  const userEnabled = usePrefsStore((s) => s.motionEnabled);
  const allowed = userEnabled && !osReduced;
  const active = useMemo(
    () => allowed && inView && tabVisible,
    [allowed, inView, tabVisible],
  );
  return { ref, active, allowed, inView, tabVisible, osReduced };
}
