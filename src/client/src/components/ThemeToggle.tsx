import type { PortalTheme } from "../theme";

interface ThemeToggleProps {
  theme: PortalTheme;
  onToggle: () => void;
}

export function ThemeToggle({ theme, onToggle }: ThemeToggleProps) {
  const nextLabel = theme === "dark" ? "Light" : "Dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={onToggle}
      aria-label={`Switch to ${nextLabel.toLowerCase()} mode`}
      title={`Switch to ${nextLabel.toLowerCase()} mode`}
    >
      {theme === "dark" ? "Light mode" : "Dark mode"}
    </button>
  );
}
