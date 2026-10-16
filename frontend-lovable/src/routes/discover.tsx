import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/components/patchwork/workspace';
import { pageMeta } from '@/lib/patchwork-data';
export const Route = createFileRoute('/discover')({
 head: () => pageMeta('Discover repositories', 'Find open-source repositories ranked by contribution fit, language, and opportunity.'),
 component: Page,
});
function Page() { return <WorkspacePage view="discover"/>; }
