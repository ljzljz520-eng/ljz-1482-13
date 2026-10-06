import clsx from "clsx";
import { useShouldAnimate } from "@/hooks/useShouldAnimate";

interface Props {
  src?: string | null;
  alt: string;
  className?: string;
  rounded?: string;
}

/**
 * Cover with a slow spotlight sweep. The animation only runs when the element
 * is in the viewport, the tab is visible, the user enabled motion in-app AND
 * the OS does not request reduced motion.
 */
const AnimatedCover = ({ src, alt, className = "", rounded = "rounded-2xl" }: Props) => {
  const { ref, active } = useShouldAnimate<HTMLDivElement>();

  return (
    <div
      ref={ref}
      className={clsx(
        "relative overflow-hidden bg-slate-100 ring-1 ring-slate-200",
        rounded,
        className,
      )}
      data-animate={active ? "on" : "off"}
    >
      {src ? (
        <>
          <img
            src={src}
            alt={alt}
            loading="lazy"
            className={clsx(
              "h-full w-full object-cover transition-transform duration-700 ease-out",
              active ? "scale-105" : "scale-100",
            )}
          />
          <div
            aria-hidden
            className={clsx(
              "pointer-events-none absolute inset-0",
              active && "animate-cover-sweep",
            )}
            style={{
              background:
                "linear-gradient(115deg, transparent 30%, rgba(255,255,255,0.28) 48%, transparent 62%)",
              backgroundSize: "220% 100%",
            }}
          />
          <div
            aria-hidden
            className={clsx(
              "pointer-events-none absolute inset-0 ring-inset ring-1 ring-white/30 transition-opacity duration-500",
              rounded,
              active ? "opacity-100" : "opacity-0",
            )}
          />
        </>
      ) : (
        <div className="flex h-full w-full items-center justify-center text-slate-400">
          <div className="text-center">
            <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-200/70 text-lg">
              🎭
            </div>
            <p className="text-xs">暂无封面</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnimatedCover;
