import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIStore {
  sidebarExpanded: boolean;
  activeRoute: string;
  selectedProspects: string[];
  onboardingProgress: number;
  viewMode: "list" | "grid" | "card";
  // Actions
  toggleSidebar: () => void;
  setSidebarExpanded: (val: boolean) => void;
  setActiveRoute: (route: string) => void;
  toggleSelectProspect: (id: string) => void;
  selectAllProspects: (ids: string[]) => void;
  clearSelectedProspects: () => void;
  setViewMode: (mode: "list" | "grid" | "card") => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      sidebarExpanded: true,
      activeRoute: "/prospect/active-queue",
      selectedProspects: [],
      onboardingProgress: 40,
      viewMode: "list",

      toggleSidebar: () =>
        set((state) => ({ sidebarExpanded: !state.sidebarExpanded })),

      setSidebarExpanded: (val) => set({ sidebarExpanded: val }),

      setActiveRoute: (route) => set({ activeRoute: route }),

      toggleSelectProspect: (id) =>
        set((state) => ({
          selectedProspects: state.selectedProspects.includes(id)
            ? state.selectedProspects.filter((p) => p !== id)
            : [...state.selectedProspects, id],
        })),

      selectAllProspects: (ids) => set({ selectedProspects: ids }),

      clearSelectedProspects: () => set({ selectedProspects: [] }),

      setViewMode: (mode) => set({ viewMode: mode }),
    }),
    {
      name: "apex-sdr-ui",
      partialize: (state) => ({
        sidebarExpanded: state.sidebarExpanded,
        viewMode: state.viewMode,
      }),
    }
  )
);
