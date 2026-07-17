export type PortalTheme = "dark" | "light";

const STORAGE_KEY = "nn-portal-theme";

export function getStoredTheme(): PortalTheme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
  } catch {
    // localStorage may be unavailable
  }
  return "dark";
}

export function applyTheme(theme: PortalTheme): void {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore persistence failures
  }
}

export function toggleTheme(current: PortalTheme): PortalTheme {
  const next: PortalTheme = current === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}
