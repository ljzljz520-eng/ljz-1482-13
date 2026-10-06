import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  token: string | null;
  hydrated: boolean;
  hydrate: () => void;
  setSession: (user: User, token: string) => void;
  logout: () => void;
}

interface Stored {
  user: User;
  token: string;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  hydrated: false,
  hydrate: () => {
    const raw = localStorage.getItem("wb_auth");
    if (raw) {
      try {
        const stored: Stored = JSON.parse(raw);
        set({ user: stored.user, token: stored.token, hydrated: true });
        return;
      } catch {
        localStorage.removeItem("wb_auth");
      }
    }
    set({ hydrated: true });
  },
  setSession: (user, token) => {
    localStorage.setItem("wb_auth", JSON.stringify({ user, token }));
    set({ user, token });
  },
  logout: () => {
    localStorage.removeItem("wb_auth");
    set({ user: null, token: null });
  },
}));
