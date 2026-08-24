// Hairlines, never shadows. Elevation is expressed by surface, not by blur.
export function Card(props: { children: React.ReactNode; className?: string; "data-testid"?: string }) {
  return (
    <div
      data-testid={props["data-testid"]}
      className={`bg-ac-surface-card border border-ac-hairline rounded-lg p-6 ${props.className ?? ""}`}
    >
      {props.children}
    </div>
  );
}
