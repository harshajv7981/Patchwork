import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/components/patchwork/workspace';
import { pageMeta } from '@/lib/patchwork-data';
export const Route = createFileRoute('/')({
 head: () => pageMeta('Workspace overview', 'Your local-first open-source contribution workspace. Discover repositories, review opportunities, and track contributions with Patchwork.'),
 component: Page,
});
function Page() { return <WorkspacePage view="overview"/>; }
