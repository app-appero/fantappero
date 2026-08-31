/**
 * Set minimo di icone evento per la match experience (EP13-P04-quater).
 *
 * Nessuna libreria icone è installata in `apps/web`/`packages/ui`: queste
 * poche SVG inline evitano di aggiungere una dipendenza solo per una manciata
 * di simboli (pallone, cartellini, sostituzione, VAR).
 *
 * Le props restano un tipo minimo dedicato (non `SVGProps<SVGSVGElement>`
 * di React) perché il monorepo risolve più copie annidate di `@types/react`
 * tra i pacchetti: estendere il tipo `Ref` ambientale di React qui
 * produrrebbe un conflitto strutturale in `apps/web` pur passando il
 * typecheck locale di `packages/ui`.
 */

type IconProps = { size?: number; className?: string };

function baseProps({ size = 14, className }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    "aria-hidden": true as const,
    focusable: false,
    className,
  };
}

export function GoalIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <circle cx="12" cy="12" r="9" fill="#fff" stroke="#111" strokeWidth="1.2" />
      <path
        d="M12 6.5 15.5 9l-1.3 4h-4.4L8.5 9Z"
        fill="#111"
      />
      <path d="M12 6.5V3.5M15.5 9l3-1M14.2 13l1.6 2.8M9.8 13l-1.6 2.8M8.5 9l-3-1" stroke="#111" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  );
}

export function OwnGoalIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <circle cx="12" cy="12" r="9" fill="#fff" stroke="#e03131" strokeWidth="1.4" />
      <path d="M12 6.5 15.5 9l-1.3 4h-4.4L8.5 9Z" fill="#e03131" />
    </svg>
  );
}

export function AssistIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <path
        d="M4 16c3-6 6-9 9-9M13 4h4v4"
        stroke="#2f6fed"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function YellowCardIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <rect x="6" y="3" width="12" height="18" rx="1.5" fill="#e6a700" />
    </svg>
  );
}

export function RedCardIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <rect x="6" y="3" width="12" height="18" rx="1.5" fill="#e03131" />
    </svg>
  );
}

export function PenaltyIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <circle cx="12" cy="12" r="9" stroke="#fff" strokeWidth="1.4" />
      <circle cx="12" cy="12" r="2.4" fill="#fff" />
    </svg>
  );
}

export function PenaltyMissedIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <circle cx="12" cy="12" r="9" stroke="#e03131" strokeWidth="1.4" />
      <path d="M9 9l6 6M15 9l-6 6" stroke="#e03131" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function SubstitutionInIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <path
        d="M12 20V6M6 11l6-6 6 6"
        stroke="#2f9e44"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SubstitutionOutIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <path
        d="M12 4v14M6 13l6 6 6-6"
        stroke="#e03131"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function VarIcon(props: IconProps) {
  return (
    <svg {...baseProps(props)} fill="none">
      <rect x="3" y="5" width="18" height="13" rx="2" stroke="#fff" strokeWidth="1.4" />
      <path d="M8 12h8M12 8v8" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
