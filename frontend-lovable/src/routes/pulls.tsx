import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/components/patchwork/workspace';
import { pageMeta } from '@/lib/patchwork-data';
export const Route = createFileRoute('/pulls')({
 head: () => pageMeta('Pull requests', 'Track patches, verification results, and the lifecycle of open-source contributions.'),
 component: Page,
});
function Page() { return <WorkspacePage view="pulls"/>; }
