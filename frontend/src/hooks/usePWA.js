import { useState, useEffect } from "react";

export function usePWA() {
  const [prompt, setPrompt] = useState(null);
  const [isInstalled, setInstalled] = useState(
    window.matchMedia("(display-mode: standalone)").matches,
  );
  useEffect(() => {
    const before = (e) => {
      e.preventDefault();
      setPrompt(e);
    };
    const installed = () => {
      setPrompt(null);
      setInstalled(true);
    };
    window.addEventListener("beforeinstallprompt", before);
    window.addEventListener("appinstalled", installed);
    return () => {
      window.removeEventListener("beforeinstallprompt", before);
      window.removeEventListener("appinstalled", installed);
    };
  }, []);
  return {
    isInstallable: !!prompt,
    isInstalled,
    promptInstall: async () => {
      if (prompt) {
        await prompt.prompt();
        await prompt.userChoice;
        setPrompt(null);
      }
    },
  };
}
