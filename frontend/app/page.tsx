import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const BUILD_INFO = {
  app: "Consulting Research Agent",
  milestone: "M1.2 — Frontend scaffold",
  next: "16.2.4",
  react: "19.2.4",
  node: process.version,
  env: process.env.NODE_ENV ?? "unknown",
} as const;

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-8 p-8 bg-background text-foreground">
      <h1 className="text-4xl font-semibold tracking-tight">
        Consulting Research Agent
      </h1>

      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Build info</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
            {Object.entries(BUILD_INFO).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="font-medium text-muted-foreground">{k}</dt>
                <dd className="font-mono">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>
    </main>
  );
}
