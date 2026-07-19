"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type WorkspaceState = {
  project: string;
  sidebarOpen: boolean;
  commandOpen: boolean;
  accessToken: string | null;
  setProject: (project: string) => void;
  toggleSidebar: () => void;
  setCommandOpen: (open: boolean) => void;
  setAccessToken: (token: string | null) => void;
};

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set) => ({
      project: "Acme.com",
      sidebarOpen: false,
      commandOpen: false,
      accessToken: null,
      setProject: (project) => set({ project }),
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setCommandOpen: (commandOpen) => set({ commandOpen }),
      setAccessToken: (accessToken) => set({ accessToken })
    }),
    {
      name: "proactive-session",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({ accessToken: state.accessToken, project: state.project })
    }
  )
);
