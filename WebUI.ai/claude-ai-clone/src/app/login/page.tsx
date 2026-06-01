"use client";

import Link from "next/link";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ClaudeTextLogo } from "@/components/claude-logo";
import { Footer } from "@/components/footer";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [isEmailSubmitted, setIsEmailSubmitted] = useState(false);
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    // In a real app, this would handle authentication
    // For this demo, we'll just simulate continuing with email
    setIsEmailSubmitted(true);
  };

  const navigateToChat = () => {
    router.push("/chat");
  };

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center">
            <Link href="/" className="inline-block">
              <ClaudeTextLogo logoSize={32} className="mx-auto" />
            </Link>

            <h1 className="mt-10 text-4xl font-normal tracking-tight">
              {isEmailSubmitted ? "Welcome back" : "Your ideas, amplified"}
            </h1>

            <p className="mt-4 text-claude-fg/80">
              {isEmailSubmitted
                ? "Enter your password to continue"
                : "Privacy-first AI that helps you create in confidence."}
            </p>
          </div>

          <div className="mt-8 bg-white p-8 rounded-xl border border-claude-border shadow-sm">
            {!isEmailSubmitted ? (
              <>
                <div className="mb-6">
                  <Button variant="outline" className="w-full flex items-center justify-center gap-2 py-6" disabled>
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M18.1711 8.36793H17.5V8.33335H10V11.6667H14.7656C14.0771 13.607 12.1867 15 10 15C7.23859 15 5.00003 12.7615 5.00003 10C5.00003 7.23857 7.23859 5.00002 10 5.00002C11.2745 5.00002 12.4347 5.48082 13.3191 6.26147L15.6741 3.90646C14.1947 2.5623 12.2149 1.66669 10 1.66669C5.39771 1.66669 1.66669 5.39771 1.66669 10C1.66669 14.6023 5.39771 18.3334 10 18.3334C14.6023 18.3334 18.3334 14.6023 18.3334 10C18.3334 9.44084 18.2746 8.89584 18.1711 8.36793Z" fill="#FFC107"/>
                      <path d="M2.62744 6.12149L5.36078 8.12941C6.10744 6.29524 7.90188 5.00002 10 5.00002C11.2745 5.00002 12.4347 5.48082 13.3191 6.26147L15.6741 3.90646C14.1947 2.5623 12.2149 1.66669 10 1.66669C6.83969 1.66669 4.10744 3.4785 2.62744 6.12149Z" fill="#FF3D00"/>
                      <path d="M10 18.3333C12.1667 18.3333 14.1021 17.4792 15.5729 16.1687L13.0021 13.9875C12.1542 14.6452 11.1109 15 10 15C7.8271 15 5.94584 13.625 5.24834 11.7021L1.51917 13.7812C2.97501 16.4729 6.15834 18.3333 10 18.3333Z" fill="#4CAF50"/>
                      <path d="M18.1708 8.36793H17.5V8.33335H10V11.6667H14.7656C14.4365 12.5806 13.824 13.3719 13.0021 13.9833L13.0031 13.9825L15.5739 16.1637C15.4073 16.3146 18.3333 14.1667 18.3333 10C18.3333 9.44084 18.2746 8.89584 18.1708 8.36793Z" fill="#1976D2"/>
                    </svg>
                    Continue with Google
                  </Button>
                </div>

                <div className="relative mb-6">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-claude-border" />
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-white text-claude-muted">OR</span>
                  </div>
                </div>

                <form onSubmit={handleSubmit}>
                  <div className="mb-6">
                    <Input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter your personal or work email"
                      className="py-6 px-4"
                      required
                    />
                  </div>

                  <Button type="submit" className="w-full py-6">
                    Continue with email
                  </Button>
                </form>

                <p className="mt-6 text-xs text-claude-muted text-center">
                  By continuing, you agree to Anthropic's{" "}
                  <Link href="/terms" className="underline hover:text-claude-fg">
                    Consumer Terms
                  </Link>{" "}
                  and{" "}
                  <Link href="/usage-policy" className="underline hover:text-claude-fg">
                    Usage Policy
                  </Link>
                  , and acknowledge our{" "}
                  <Link href="/privacy" className="underline hover:text-claude-fg">
                    Privacy Policy
                  </Link>
                  .
                </p>
              </>
            ) : (
              <>
                <form onSubmit={(e) => {
                  e.preventDefault();
                  // In a real app, this would validate the password
                  navigateToChat();
                }}>
                  <div className="mb-6">
                    <p className="mb-1 font-medium">{email}</p>
                    <Input
                      type="password"
                      placeholder="Password"
                      className="py-6 px-4"
                      required
                    />
                  </div>

                  <Button type="submit" className="w-full py-6">
                    Sign in
                  </Button>

                  <div className="mt-4 text-center">
                    <button
                      type="button"
                      className="text-sm text-claude-fg underline"
                      onClick={() => setIsEmailSubmitted(false)}
                    >
                      Use a different email
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>

          <div className="mt-8 text-center">
            <button
              type="button"
              onClick={navigateToChat}
              className="text-sm text-claude-fg underline"
            >
              Learn more
            </button>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
