import { useState } from "react";

// Buttons name their effect and keep the word through the flow: "Activate" ->
// "Activated", never a generic spinner.
const VARIANT: Record<"primary" | "secondary" | "ghost", string> = {
  primary: "bg-ac-primary text-ac-on-primary hover:bg-ac-primary-active",
  secondary: "bg-transparent text-ac-ink border border-ac-hairline-strong hover:bg-ac-surface-sunk",
  ghost: "bg-transparent text-ac-body hover:text-ac-ink hover:bg-ac-surface-sunk",
};

export function Button(props: {
  variant?: "primary" | "secondary" | "ghost";
  label: string;
  pendingLabel?: string;
  doneLabel?: string;
  onClick?: () => void | Promise<void>;
  disabled?: boolean;
}) {
  const variant = props.variant ?? "primary";
  const [state, setState] = useState<"idle" | "pending" | "done">("idle");

  const handleClick = async () => {
    if (!props.onClick) return;
    if (props.pendingLabel) setState("pending");
    try {
      await props.onClick();
      setState(props.doneLabel ? "done" : "idle");
    } catch (err) {
      // A rejected onClick (the caller's own request failed) used to leave
      // the button stuck on pendingLabel forever if the caller didn't catch
      // its own error, or -- if the caller swallowed the error internally --
      // to unconditionally show doneLabel here even though nothing
      // succeeded. Reset to idle either way so the button reflects reality
      // and can be retried; the caller is still responsible for surfacing
      // its own error message.
      setState("idle");
      throw err;
    }
  };

  const label =
    state === "pending" ? props.pendingLabel ?? props.label
      : state === "done" ? props.doneLabel ?? props.label
      : props.label;

  return (
    <button
      type="button"
      disabled={props.disabled || state === "pending"}
      onClick={handleClick}
      className={`h-10 px-[18px] rounded-md text-button transition-colors duration-micro ${VARIANT[variant]}`}
    >
      {label}
    </button>
  );
}
