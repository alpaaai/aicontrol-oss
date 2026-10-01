interface ReactivateBannerProps {
  manageSubscriptionUrl: string | null;
  title?: string;
  description?: string;
}

export function ReactivateBanner({
  manageSubscriptionUrl,
  title = 'Reactivate your plan',
  description = 'Your subscription needs attention before paid features can keep running.',
}: ReactivateBannerProps) {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 space-y-3">
      <h2 className="text-lg font-semibold text-amber-900">{title}</h2>
      <p className="text-sm text-amber-800">{description}</p>
      {manageSubscriptionUrl && (
        <a
          href={manageSubscriptionUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-md text-sm font-medium"
        >
          Reactivate
        </a>
      )}
    </div>
  );
}
