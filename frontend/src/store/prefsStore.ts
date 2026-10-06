import { create } from "zustand";

interface PrefsState {
  motionEnabled: boolean;
  toggleMotion: () => void;
  setMotion: (v: boolean) => void;
}

const STORAGE_KEY = "wb_prefs";

function readInitial(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw).motionEnabled !== false;
  } catch {
    /* ignore */
  }
  return true;
}

export const usePrefsStore = create<PrefsState>((set, get) => ({
  motionEnabled: readInitial(),
  toggleMotion: () => {
    const next = !get().motionEnabled;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ motionEnabled: next }));
    set({ motionEnabled: next });
  },
  setMotion: (v) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ motionEnabled: v }));
    set({ motionEnabled: v });
  },
}));
