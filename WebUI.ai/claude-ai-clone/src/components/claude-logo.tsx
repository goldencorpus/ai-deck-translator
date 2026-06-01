import { cn } from "@/lib/utils";

interface ClaudeLogoProps extends React.SVGProps<SVGSVGElement> {
  size?: number;
  className?: string;
}

export function ClaudeLogo({
  size = 24,
  className,
  ...props
}: ClaudeLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("text-claude-sunburst", className)}
      {...props}
    >
      <path
        d="M12 17.75C15.1756 17.75 17.75 15.1756 17.75 12C17.75 8.82436 15.1756 6.25 12 6.25C8.82436 6.25 6.25 8.82436 6.25 12C6.25 15.1756 8.82436 17.75 12 17.75Z"
        fill="currentColor"
      />
      <path
        d="M12 5.25C12.4142 5.25 12.75 4.91421 12.75 4.5V2C12.75 1.58579 12.4142 1.25 12 1.25C11.5858 1.25 11.25 1.58579 11.25 2V4.5C11.25 4.91421 11.5858 5.25 12 5.25Z"
        fill="currentColor"
      />
      <path
        d="M12 18.75C11.5858 18.75 11.25 19.0858 11.25 19.5V22C11.25 22.4142 11.5858 22.75 12 22.75C12.4142 22.75 12.75 22.4142 12.75 22V19.5C12.75 19.0858 12.4142 18.75 12 18.75Z"
        fill="currentColor"
      />
      <path
        d="M18.75 12C18.75 11.5858 19.0858 11.25 19.5 11.25H22C22.4142 11.25 22.75 11.5858 22.75 12C22.75 12.4142 22.4142 12.75 22 12.75H19.5C19.0858 12.75 18.75 12.4142 18.75 12Z"
        fill="currentColor"
      />
      <path
        d="M5.25 12C5.25 12.4142 4.91421 12.75 4.5 12.75H2C1.58579 12.75 1.25 12.4142 1.25 12C1.25 11.5858 1.58579 11.25 2 11.25H4.5C4.91421 11.25 5.25 11.5858 5.25 12Z"
        fill="currentColor"
      />
      <path
        d="M17.0104 7.75736C17.3033 7.46447 17.7782 7.46447 18.0711 7.75736L19.8388 9.52513C20.1317 9.81802 20.1317 10.2929 19.8388 10.5858C19.5459 10.8787 19.071 10.8787 18.7781 10.5858L17.0104 8.81802C16.7175 8.52513 16.7175 8.05025 17.0104 7.75736Z"
        fill="currentColor"
      />
      <path
        d="M6.98956 16.2426C6.69667 16.5355 6.22179 16.5355 5.9289 16.2426L4.16113 14.4749C3.86824 14.182 3.86824 13.7071 4.16113 13.4142C4.45402 13.1213 4.9289 13.1213 5.22179 13.4142L6.98956 15.182C7.28245 15.4749 7.28245 15.9497 6.98956 16.2426Z"
        fill="currentColor"
      />
      <path
        d="M7.75736 6.98956C7.46447 6.69667 7.46447 6.22179 7.75736 5.9289L9.52513 4.16113C9.81802 3.86824 10.2929 3.86824 10.5858 4.16113C10.8787 4.45402 10.8787 4.9289 10.5858 5.22179L8.81802 6.98956C8.52513 7.28245 8.05025 7.28245 7.75736 6.98956Z"
        fill="currentColor"
      />
      <path
        d="M16.2426 17.0104C16.5355 17.3033 16.5355 17.7782 16.2426 18.0711L14.4749 19.8388C14.182 20.1317 13.7071 20.1317 13.4142 19.8388C13.1213 19.5459 13.1213 19.071 13.4142 18.7781L15.182 17.0104C15.4749 16.7175 15.9497 16.7175 16.2426 17.0104Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function ClaudeTextLogo({
  className,
  logoSize = 24,
  ...props
}: {
  className?: string;
  logoSize?: number;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center gap-2", className)}
      {...props}
    >
      <ClaudeLogo size={logoSize} />
      <span className="font-medium text-xl">Claude</span>
    </div>
  );
}
