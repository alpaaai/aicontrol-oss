// The only place magenta appears at scale. A chip is always editable -- if a
// value cannot be changed it is set as plain ink, never as a chip. That rule
// is what makes the colour mean something.
export function PolicyChip(props: {
  children: React.ReactNode;
  editable?: boolean;
  onClick?: () => void;
}) {
  const className =
    "inline-flex items-center bg-ac-primary-soft text-ac-primary-active text-identifier " +
    "rounded-chip px-[10px] py-1 hover:bg-[#FFD9E8] focus:outline focus:outline-2 " +
    "focus:outline-ac-primary focus:outline-offset-2";

  if (props.editable) {
    return (
      <button type="button" onClick={props.onClick} className={className + " cursor-text"}>
        {props.children}
      </button>
    );
  }
  return <span className={className}>{props.children}</span>;
}
