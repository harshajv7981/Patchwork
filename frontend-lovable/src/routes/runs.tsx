import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/components/patchwork/workspace';
import { pageMeta } from '@/lib/patchwork-data';
export const Route = createFileRoute('/runs')({
 head: () => pageMeta('Runs and history', 'Review discovery runs and your autonomous contribution activity in Patchwork.'),
 component: Page,
});
function Page() { return <WorkspacePage view="runs"/>; }
