import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/components/patchwork/workspace';
import { pageMeta } from '@/lib/patchwork-data';
export const Route = createFileRoute('/ideas')({
 head: () => pageMeta('Feature ideas', 'Review architectural improvements and high-impact feature proposals in Patchwork.'),
 component: Page,
});
function Page() { return <WorkspacePage view="ideas"/>; }
