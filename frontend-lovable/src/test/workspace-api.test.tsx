import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryHistory, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkspacePage, WorkspaceShell } from "@/components/patchwork/workspace";

const api: Record<string, unknown> = {
  "/api/repositories?language=": [{ full_name: "encode/httpx", owner: "encode", name: "httpx", description: "HTTP client", language: "Python", stars: 13800, open_issues: 7, fit_score: 92, trend_percent: 4, url: "https://github.com/encode/httpx" }],
  "/api/health": { status: "ok", ollama_connected: true, configured_model: "test-model", model_available: true, provider: "ollama" },
};

function renderAt(path: string, view: "discover" | "pulls") {
  const rootRoute = createRootRoute({ component: WorkspaceShell });
  const page = createRoute({ getParentRoute: () => rootRoute, path, component: () => <WorkspacePage view={view} /> });
  const router = createRouter({ routeTree: rootRoute.addChildren([page]), history: createMemoryHistory({ initialEntries: [path] }) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

afterEach(() => vi.unstubAllGlobals());

describe("workspace talks to the Patchwork API", () => {
  it("renders repositories and model from the API", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const body = api[url.replace("http://localhost:8000", "")];
      return new Response(JSON.stringify(body ?? []), { status: body === undefined && !url.includes("?") ? 404 : 200 });
    }));
    renderAt("/discover", "discover");

    expect(await screen.findByText("httpx")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Explore repo/ })).toHaveAttribute("href", "https://github.com/encode/httpx");
    expect((await screen.findAllByText("test-model")).length).toBeGreaterThan(0);
  });

  it("shows the backend error when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "boom" }), { status: 500 })));
    renderAt("/pulls", "pulls");

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
