import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/components/patchwork/workspace';
import { pageMeta } from '@/lib/patchwork-data';
export const Route = createFileRoute('/issues')({
 head: () => pageMeta('Candidate issues', 'Explore and analyze open-source issues ranked by contribution suitability.'),
 component: Page,
});
function Page() { return <WorkspacePage view="issues"/>; }
