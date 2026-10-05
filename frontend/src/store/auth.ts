import { create } from "zustand";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  setUser: (u: User | null) => void;
  logout: () => void;
}

const stored = (() => {
  try {
    const raw = localStorage.getItem("cs_user");
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
})();

export const useAuth = create<AuthState>((set) => ({
  user: stored,
  setUser: (u) => {
    if (u) localStorage.setItem("cs_user", JSON.stringify(u));
    else localStorage.removeItem("cs_user");
    set({ user: u });
  },
  logout: () => {
    localStorage.removeItem("cs_token");
    localStorage.removeItem("cs_user");
    set({ user: null });
  },
}));

export const canEdit = (u: User | null) => u?.role === "admin" || u?.role === "editor";
export const isAdmin = (u: User | null) => u?.role === "admin";
