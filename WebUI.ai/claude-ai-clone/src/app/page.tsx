import Link from "next/link";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Header } from "@/components/header";
import { Footer } from "@/components/footer";
import { ClaudeLogo } from "@/components/claude-logo";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      <Header />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="py-20 md:py-28">
          <div className="claude-container">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between">
              <div className="mb-10 md:mb-0 md:w-1/2 md:pr-8">
                <h1 className="text-4xl md:text-6xl font-normal tracking-tight mb-6">
                  Your ideas,
                  <br />
                  amplified
                </h1>
                <p className="text-lg md:text-xl mb-8 text-claude-fg/90">
                  Privacy-first AI that helps you create in confidence.
                </p>
                <div className="flex flex-col sm:flex-row gap-4">
                  <Link href="/login">
                    <Button className="w-full sm:w-auto rounded-full" size="lg">
                      Get started
                    </Button>
                  </Link>
                  <Link href="/chat">
                    <Button variant="outline" className="w-full sm:w-auto rounded-full" size="lg">
                      Try Claude
                    </Button>
                  </Link>
                </div>
              </div>

              <div className="md:w-1/2 flex justify-center md:justify-end">
                <div className="bg-white/90 rounded-xl p-4 border border-claude-border shadow-sm w-full max-w-md">
                  <div className="bg-claude-bg/60 rounded-lg p-4 flex items-start gap-3">
                    <ClaudeLogo size={20} />
                    <p className="text-sm">
                      Claude, make a content calendar for my marketing campaign.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Meet Claude Section */}
        <section className="py-16 md:py-24 border-t border-claude-border">
          <div className="claude-container">
            <h2 className="text-3xl md:text-4xl font-normal text-center mb-6">
              Meet Claude
            </h2>
            <p className="text-lg text-center text-claude-fg/90 max-w-3xl mx-auto mb-16">
              Claude is a next generation AI assistant built by Anthropic and trained to be safe, accurate, and secure to help you do your best work.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <Card className="bg-white/80">
                <CardHeader>
                  <CardTitle>Create with Claude</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-claude-fg/90">
                    Draft and iterate on websites, graphics, documents, and code alongside your chat with Artifacts.
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-white/80">
                <CardHeader>
                  <CardTitle>Bring your knowledge</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-claude-fg/90">
                    Upload files and documents to provide context and get more accurate, relevant responses.
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-white/80">
                <CardHeader>
                  <CardTitle>Share and collaborate</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-claude-fg/90">
                    Work together with your team on projects and share conversations to improve productivity.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        {/* Pricing Section */}
        <section className="py-16 md:py-24 border-t border-claude-border">
          <div className="claude-container">
            <h2 className="text-3xl md:text-4xl font-normal text-center mb-6">
              Explore plans
            </h2>

            <Tabs defaultValue="individual" className="max-w-3xl mx-auto">
              <div className="flex justify-center mb-8">
                <TabsList className="rounded-full">
                  <TabsTrigger value="individual" className="rounded-full">Individual</TabsTrigger>
                  <TabsTrigger value="team" className="rounded-full">Team & Enterprise</TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="individual">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                  <Card>
                    <CardHeader>
                      <CardTitle>Free</CardTitle>
                      <CardDescription>Try Claude</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold mb-6">$0</div>
                      <ul className="space-y-2">
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Chat on web, iOS, and Android</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Generate code and visualize data</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Write, edit, and create content</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Analyze text and images</span>
                        </li>
                      </ul>
                    </CardContent>
                    <CardFooter>
                      <Link href="/signup" className="w-full">
                        <Button variant="outline" className="w-full">Get started</Button>
                      </Link>
                    </CardFooter>
                  </Card>

                  <Card className="border-claude-sunburst">
                    <CardHeader>
                      <CardTitle>Pro</CardTitle>
                      <CardDescription>For everyday productivity</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold mb-6">$17</div>
                      <p className="text-xs text-claude-muted mb-6">
                        Per month with annual subscription discount; $200 billed up front. $20 if billed monthly.
                      </p>
                      <ul className="space-y-2">
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Everything in Free, plus:</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>More usage</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Access to Projects to organize chats and documents</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Ability to use more Claude models</span>
                        </li>
                      </ul>
                    </CardContent>
                    <CardFooter>
                      <Link href="/signup" className="w-full">
                        <Button className="w-full">Subscribe</Button>
                      </Link>
                    </CardFooter>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Max</CardTitle>
                      <CardDescription>5-20x more usage than Pro</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-3xl font-bold mb-6">From $100</div>
                      <p className="text-xs text-claude-muted mb-6">
                        Per month billed monthly
                      </p>
                      <ul className="space-y-2">
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Everything in Pro, plus:</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Substantially more usage to work with Claude</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Scale usage based on specific needs</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <span className="text-claude-sunburst">•</span>
                          <span>Priority access during high traffic periods</span>
                        </li>
                      </ul>
                    </CardContent>
                    <CardFooter>
                      <Link href="/signup" className="w-full">
                        <Button variant="outline" className="w-full">Contact sales</Button>
                      </Link>
                    </CardFooter>
                  </Card>
                </div>
                <p className="text-xs text-claude-muted text-center mt-6">
                  Prices shown do not include applicable tax.
                </p>
              </TabsContent>

              <TabsContent value="team">
                <div className="text-center py-12">
                  <h3 className="text-2xl font-medium mb-4">Claude for Work</h3>
                  <p className="text-claude-fg/90 mb-8 max-w-xl mx-auto">
                    Get enterprise-grade security, admin controls, and team collaboration features with Claude for Work.
                  </p>
                  <div className="flex justify-center">
                    <Link href="/contact-sales">
                      <Button size="lg" className="rounded-full">Contact sales</Button>
                    </Link>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </section>

        {/* FAQ Section */}
        <section className="py-16 md:py-24 border-t border-claude-border">
          <div className="claude-container">
            <h2 className="text-3xl md:text-4xl font-normal text-center mb-12">
              Frequently asked questions
            </h2>

            <div className="max-w-3xl mx-auto space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg font-medium">What is Claude and how does it work?</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-claude-fg/90">
                    Claude is an AI assistant created by Anthropic, designed to be helpful, harmless, and honest. It uses a technique called Constitutional AI to provide safe and helpful responses while avoiding harmful content.
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg font-medium">What should I use Claude for?</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-claude-fg/90">
                    Claude can help with writing, brainstorming, coding, answering questions, summarizing documents, and many other tasks. It's great for productivity, creative work, and learning new subjects.
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg font-medium">How much does it cost to use?</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-claude-fg/90">
                    Claude offers a free plan with limited usage, a Pro plan at $17/month (billed annually) or $20/month (billed monthly), and a Max plan starting at $100/month for higher usage needs.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-16 md:py-24 bg-white/70">
          <div className="claude-container text-center">
            <h2 className="text-3xl md:text-4xl font-normal mb-6">
              Ready to try Claude?
            </h2>
            <p className="text-lg text-claude-fg/90 max-w-2xl mx-auto mb-8">
              Get started with Claude today and experience the next generation AI assistant.
            </p>
            <div className="flex flex-col sm:flex-row justify-center gap-4">
              <Link href="/login">
                <Button size="lg" className="w-full sm:w-auto rounded-full">
                  Sign up for free
                </Button>
              </Link>
              <Link href="/chat">
                <Button variant="outline" size="lg" className="w-full sm:w-auto rounded-full">
                  Try Claude
                </Button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
