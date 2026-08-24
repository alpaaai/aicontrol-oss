// An invitation, never a blank. Written in the interface's voice.
export function EmptyState(props: { title: string; action?: React.ReactNode }) {
  return (
    <div className="text-center py-12">
      <p className="text-title-lg text-ac-muted">{props.title}</p>
      {props.action && <div className="mt-4 flex justify-center">{props.action}</div>}
    </div>
  );
}
