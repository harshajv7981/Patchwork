import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/components/patchwork/workspace';
import { pageMeta } from '@/lib/patchwork-data';
export const Route = createFileRoute('/settings')({
 head: () => pageMeta('Workspace settings', 'Configure the local environment and model preferences for your Patchwork workspace.'),
 component: Page,
});
function Page() { return <WorkspacePage view="settings"/>; }
