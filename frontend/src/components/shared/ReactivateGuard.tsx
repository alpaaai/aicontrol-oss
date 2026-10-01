import { Link } from 'react-router-dom';

interface ReactivateGuardProps {
  title: string;
  description: string;
}

// Blocks a paid route's normal content when the org's subscription needs
// attention (past_due/canceled/unreachable) -- distinct from EnterpriseLock,
// which handles "never subscribed to this tier" (plans/v4 task 25).
export function ReactivateGuard({ title, description }: ReactivateGuardProps) {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 space-y-3 max-w-xl">
      <h2 className="text-lg font-semibold text-amber-900">{title}</h2>
      <p className="text-sm text-amber-800">{description}</p>
      <Link
        to="/billing"
        className="inline-flex px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-md text-sm font-medium"
      >
        Go to Billing
      </Link>
    </div>
  );
}
