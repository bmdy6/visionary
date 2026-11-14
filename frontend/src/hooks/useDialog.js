import { useEffect, useRef } from "react";

// Keep keyboard navigation inside the topmost dialog and restore its opener.
export default function useDialog(onClose) {
  const ref = useRef(null);
  useEffect(() => {
    const opener = document.activeElement;
    const root = ref.current;
    const key = (event) => {
      const dialogs = [...document.querySelectorAll('[aria-modal="true"]')];
      if (dialogs.at(-1) !== root) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }
      if (event.key !== "Tab") return;
      const controls = [
        ...root.querySelectorAll(
          "button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)",
        ),
      ].filter((el) => el.getClientRects().length);
      if (!controls.length) return;
      const first = controls[0],
        last = controls.at(-1);
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          !root.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          !root.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", key);
    root?.querySelector("button, input")?.focus();
    return () => {
      document.removeEventListener("keydown", key);
      if (
        opener?.isConnected &&
        (root?.contains(document.activeElement) ||
          document.activeElement === document.body)
      )
        opener.focus();
    };
  }, [onClose]);
  return ref;
}
