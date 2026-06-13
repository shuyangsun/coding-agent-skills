import { Monitor, Moon, Sun } from "lucide-react";

import { type ThemePref, useTheme, setThemePref } from "#/lib/theme";
import { Segmented } from "#/components/ui";

const ICONS: Record<ThemePref, typeof Sun> = {
  light: Sun,
  system: Monitor,
  dark: Moon,
};

export function ThemeToggle() {
  const { pref } = useTheme();
  return (
    <Segmented<ThemePref>
      ariaLabel="Color theme"
      size="sm"
      value={pref}
      onChange={setThemePref}
      options={(["light", "system", "dark"] as const).map((value) => {
        const Icon = ICONS[value];
        return {
          value,
          title: `${value[0].toUpperCase()}${value.slice(1)} theme`,
          label: <Icon className="h-3.5 w-3.5" />,
        };
      })}
    />
  );
}
