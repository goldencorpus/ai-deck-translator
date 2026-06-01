import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ClaudeTextLogo } from "@/components/claude-logo";

export function Header() {
  return (
    <header className="border-b border-claude-border py-4">
      <div className="claude-container flex items-center justify-between">
        <div className="flex items-center space-x-8">
          <Link href="/" className="flex items-center">
            <ClaudeTextLogo logoSize={28} />
          </Link>

          <nav className="hidden md:flex items-center space-x-6">
            <Link
              href="/features"
              className="text-sm text-claude-fg/80 hover:text-claude-fg transition-colors"
            >
              Features
            </Link>
            <Link
              href="/pricing"
              className="text-sm text-claude-fg/80 hover:text-claude-fg transition-colors"
            >
              Pricing
            </Link>
            <Link
              href="/about"
              className="text-sm text-claude-fg/80 hover:text-claude-fg transition-colors"
            >
              About Claude
            </Link>
          </nav>
        </div>

        <div className="flex items-center space-x-4">
          <Link href="/chat">
            <Button variant="outline" size="sm" className="rounded-full">
              Try Claude
            </Button>
          </Link>
          <Link href="/login">
            <Button size="sm" className="rounded-full">
              Sign in
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}
