import { useSyncExternalStore } from "react";

export const THEME_PREFS = ["light", "system", "dark"] as const;
export type ThemePref = (typeof THEME_PREFS)[number];
export type Resolved = "light" | "dark";

const KEY = "inception-theme";
const listeners = new Set<() => void>();

function systemDark(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function readPref(): ThemePref {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(KEY);
  return stored === "light" || stored === "dark" || stored === "system"
    ? stored
    : "system";
}

function resolve(pref: ThemePref): Resolved {
  if (pref === "system") return systemDark() ? "dark" : "light";
  return pref;
}

function apply(pref: ThemePref): void {
  if (typeof document === "undefined") return;
  const resolved = resolve(pref);
  document.documentElement.classList.toggle("dark", resolved === "dark");
  document.documentElement.style.colorScheme = resolved;
}

export function setThemePref(pref: ThemePref): void {
  try {
    window.localStorage.setItem(KEY, pref);
  } catch {
    // private mode / storage disabled — still apply for this session
  }
  apply(pref);
  for (const listener of listeners) listener();
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  // Track OS theme changes while in "system" mode.
  const mq =
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-color-scheme: dark)")
      : null;
  const onSystem = () => {
    if (readPref() === "system") apply("system");
    onChange();
  };
  mq?.addEventListener("change", onSystem);
  return () => {
    listeners.delete(onChange);
    mq?.removeEventListener("change", onSystem);
  };
}

export type ThemeView = { pref: ThemePref; resolved: Resolved };

// Cache the snapshot object so getSnapshot returns a stable reference until a
// real change occurs (useSyncExternalStore requires referential stability).
let snapshot: ThemeView = { pref: "system", resolved: "light" };
function getSnapshot(): ThemeView {
  const pref = readPref();
  const resolved = resolve(pref);
  if (pref !== snapshot.pref || resolved !== snapshot.resolved) {
    snapshot = { pref, resolved };
  }
  return snapshot;
}

const serverSnapshot: ThemeView = { pref: "system", resolved: "light" };

export function useTheme(): ThemeView {
  return useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot);
}

/** Inlined into <head> before paint so the theme is correct with no flash. */
export const THEME_INIT_SCRIPT = `(function(){try{var k=localStorage.getItem("${KEY}");var d=k==="dark"||((k===null||k==="system")&&matchMedia("(prefers-color-scheme: dark)").matches);var e=document.documentElement;e.classList.toggle("dark",d);e.style.colorScheme=d?"dark":"light";}catch(_){}})();`;
