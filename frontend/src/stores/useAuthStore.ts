import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { apiClient } from '../api/client';

export type AuthUser = {
  id: string;
  username: string;
  role: 'admin' | 'user' | string;
  is_active: boolean;
  daily_task_limit: number;
  created_at?: string | null;
};

type AuthState = {
  token?: string;
  user?: AuthUser;
  hydrated: boolean;
  authLoading: boolean;
  setSession: (token: string, user: AuthUser) => void;
  clearSession: () => void;
  markHydrated: () => void;
  bootstrap: () => Promise<void>;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: undefined,
      user: undefined,
      hydrated: false,
      authLoading: false,
      setSession: (token, user) => set({ token, user }),
      clearSession: () => set({ token: undefined, user: undefined, authLoading: false }),
      markHydrated: () => set({ hydrated: true }),
      bootstrap: async () => {
        if (!get().token) {
          set({ user: undefined, authLoading: false });
          return;
        }
        set({ authLoading: true });
        try {
          const response = await apiClient.get<AuthUser>('/auth/me');
          set({ user: response.data });
        } catch {
          set({ token: undefined, user: undefined });
        } finally {
          set({ authLoading: false });
        }
      },
    }),
    {
      name: 'leadgen-auth',
      partialize: (state) => ({ token: state.token, user: state.user }),
      onRehydrateStorage: () => (state) => {
        state?.markHydrated();
      },
    },
  ),
);
