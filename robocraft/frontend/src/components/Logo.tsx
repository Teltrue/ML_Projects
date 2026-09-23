export default function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect x="1" y="1" width="30" height="30" rx="8" fill="#0c121c" stroke="#3dd6ec" strokeOpacity="0.5" />
      <path
        d="M8 24 L8 19 L14 12 L21 15"
        fill="none"
        stroke="#e6ebf3"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="19" r="2.2" fill="#3dd6ec" />
      <circle cx="14" cy="12" r="2.2" fill="#3dd6ec" />
      <path d="M21 15 l3 -2.5 M21 15 l3 2.5" stroke="#3dd6ec" strokeWidth="2" strokeLinecap="round" />
      <rect x="5" y="24" width="7" height="2.5" rx="1" fill="#7d8ba3" />
    </svg>
  );
}
