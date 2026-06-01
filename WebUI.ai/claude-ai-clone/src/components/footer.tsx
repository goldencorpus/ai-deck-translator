import Link from "next/link";
import { Separator } from "@/components/ui/separator";
import { ClaudeLogo } from "@/components/claude-logo";

export function Footer() {
  return (
    <footer className="bg-claude-bg border-t border-claude-border py-12">
      <div className="claude-container">
        <div className="flex flex-col md:flex-row justify-between mb-12">
          <div className="mb-8 md:mb-0">
            <Link href="/" className="flex items-center">
              <ClaudeLogo size={32} />
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div className="space-y-4">
              <h3 className="font-medium text-sm">Product</h3>
              <ul className="space-y-3">
                <li>
                  <Link
                    href="/features"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Features
                  </Link>
                </li>
                <li>
                  <Link
                    href="/pricing"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Pricing
                  </Link>
                </li>
                <li>
                  <Link
                    href="/api"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    API
                  </Link>
                </li>
              </ul>
            </div>

            <div className="space-y-4">
              <h3 className="font-medium text-sm">Company</h3>
              <ul className="space-y-3">
                <li>
                  <Link
                    href="/about"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    About
                  </Link>
                </li>
                <li>
                  <Link
                    href="/careers"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Careers
                  </Link>
                </li>
                <li>
                  <Link
                    href="/blog"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Blog
                  </Link>
                </li>
              </ul>
            </div>

            <div className="space-y-4">
              <h3 className="font-medium text-sm">Support</h3>
              <ul className="space-y-3">
                <li>
                  <Link
                    href="/help"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Help Center
                  </Link>
                </li>
                <li>
                  <Link
                    href="/contact"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Contact
                  </Link>
                </li>
                <li>
                  <Link
                    href="/status"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Status
                  </Link>
                </li>
              </ul>
            </div>

            <div className="space-y-4">
              <h3 className="font-medium text-sm">Legal</h3>
              <ul className="space-y-3">
                <li>
                  <Link
                    href="/terms"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Terms
                  </Link>
                </li>
                <li>
                  <Link
                    href="/privacy"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Privacy
                  </Link>
                </li>
                <li>
                  <Link
                    href="/responsible-use"
                    className="text-sm text-claude-muted hover:text-claude-fg transition-colors"
                  >
                    Responsible Use
                  </Link>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <Separator />

        <div className="mt-8 flex flex-col md:flex-row justify-between items-center">
          <p className="text-sm text-claude-muted mb-4 md:mb-0">
            © {new Date().getFullYear()} Anthropic, PBC. All rights reserved.
          </p>
          <div className="flex space-x-6">
            <Link
              href="https://twitter.com/AnthropicAI"
              target="_blank"
              rel="noopener noreferrer"
              className="text-claude-muted hover:text-claude-fg transition-colors"
            >
              Twitter
            </Link>
            <Link
              href="https://github.com/anthropics"
              target="_blank"
              rel="noopener noreferrer"
              className="text-claude-muted hover:text-claude-fg transition-colors"
            >
              GitHub
            </Link>
            <Link
              href="https://www.linkedin.com/company/anthropic-ai"
              target="_blank"
              rel="noopener noreferrer"
              className="text-claude-muted hover:text-claude-fg transition-colors"
            >
              LinkedIn
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
