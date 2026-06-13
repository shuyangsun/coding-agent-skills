import { createFileRoute } from "@tanstack/react-router";
import { ServerCrash } from "lucide-react";

import { listProjects } from "#/server/rag";
import { App } from "#/components/app";

export const Route = createFileRoute("/")({
  loader: () => listProjects(),
  component: Home,
  errorComponent: LoaderError,
});

function Home() {
  const projects = Route.useLoaderData();
  return <App projects={projects} />;
}

function LoaderError({ error }: { error: Error }) {
  return (
    <div className="grid min-h-dvh place-items-center p-6">
      <div className="max-w-md rounded-2xl border border-danger/40 bg-danger-soft p-6 text-center">
        <ServerCrash className="mx-auto mb-3 h-8 w-8 text-danger" />
        <h1 className="text-base font-semibold text-fg">
          Cannot reach the RAG service
        </h1>
        <p className="mt-2 break-words font-mono text-xs text-fg/80">
          {error.message}
        </p>
        <p className="mt-3 text-sm text-muted">
          Start the sidecar and dev server together with{" "}
          <code className="rounded bg-code px-1.5 py-0.5 font-mono text-xs">
            bun run dev
          </code>
          .
        </p>
      </div>
    </div>
  );
}
