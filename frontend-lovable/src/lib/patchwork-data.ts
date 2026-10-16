export type WorkspaceView = 'overview' | 'discover' | 'ideas' | 'issues' | 'pulls' | 'runs' | 'settings';
export const repositories = [
 { id: 'fastapi', owner: 'fastapi', name: 'fastapi', description: 'FastAPI framework, high performance, easy to learn, fast to code, ready for production.', language: 'Python', stars: '78.2k', forks: '6.8k', issues: 24, fit: 98, icon: 'bolt' },
 { id: 'pydantic', owner: 'pydantic', name: 'pydantic', description: 'Data validation using Python type hints. Fast and extensible, with developer-friendly errors.', language: 'Python', stars: '23.1k', forks: '2.1k', issues: 18, fit: 96, icon: 'braces' },
 { id: 'ruff', owner: 'astral-sh', name: 'ruff', description: 'An extremely fast Python linter and code formatter, written in Rust.', language: 'Rust', stars: '38.6k', forks: '1.4k', issues: 32, fit: 94, icon: 'ruff' },
 { id: 'httpx', owner: 'encode', name: 'httpx', description: 'A next generation HTTP client for Python with synchronous and asynchronous APIs.', language: 'Python', stars: '13.8k', forks: '920', issues: 16, fit: 92, icon: 'globe' },
 { id: 'tanstack', owner: 'TanStack', name: 'query', description: 'Powerful asynchronous state management for web applications.', language: 'TypeScript', stars: '46.3k', forks: '3.4k', issues: 21, fit: 91, icon: 'braces' },
 { id: 'polars', owner: 'pola-rs', name: 'polars', description: 'A lightning-fast DataFrame library for expressive data manipulation.', language: 'Rust', stars: '31.9k', forks: '1.9k', issues: 27, fit: 90, icon: 'globe' },
];
export const ideas = [
 { title: 'Add retry support for transient HTTP failures', repo: 'encode / httpx', category: 'Reliability', impact: 94, complexity: 'Intermediate', description: 'Introduce configurable retry policies with exponential backoff for connection errors and transient server responses.' },
 { title: 'Improve validation error context', repo: 'pydantic / pydantic', category: 'Developer experience', impact: 91, complexity: 'Intermediate', description: 'Include field paths and actionable suggestions in nested model validation errors.' },
 { title: 'Cache dependency resolution results', repo: 'fastapi / fastapi', category: 'Performance', impact: 88, complexity: 'Advanced', description: 'Reduce repeated dependency graph traversals while preserving request-scoped behavior.' },
];
export const candidateIssues = [
 { title: 'Respect timeout settings in streaming responses', repo: 'encode / httpx', number: 3291, score: 96, label: 'good first issue', language: 'Python' },
 { title: 'Improve error message for invalid Union types', repo: 'pydantic / pydantic', number: 10842, score: 94, label: 'help wanted', language: 'Python' },
 { title: 'Handle optional query parameters in OpenAPI schema', repo: 'fastapi / fastapi', number: 12708, score: 92, label: 'good first issue', language: 'Python' },
 { title: 'Add autofix for redundant parentheses', repo: 'astral-sh / ruff', number: 14326, score: 89, label: 'help wanted', language: 'Rust' },
 { title: 'Support custom serialization contexts', repo: 'pydantic / pydantic', number: 10917, score: 87, label: 'enhancement', language: 'Python' },
 { title: 'Document connection pooling behavior', repo: 'encode / httpx', number: 3312, score: 84, label: 'documentation', language: 'Python' },
 { title: 'Cache parsed dependency graphs between requests', repo: 'fastapi / fastapi', number: 12744, score: 82, label: 'performance', language: 'Python' },
 { title: 'Warn on unused suppression comments', repo: 'astral-sh / ruff', number: 14351, score: 80, label: 'good first issue', language: 'Rust' },
 { title: 'Allow per-request event hooks', repo: 'encode / httpx', number: 3325, score: 78, label: 'enhancement', language: 'Python' },
 { title: 'Improve error span for nested discriminated unions', repo: 'pydantic / pydantic', number: 10933, score: 75, label: 'developer experience', language: 'Python' },
 { title: 'Parallelize static dependency resolution', repo: 'fastapi / fastapi', number: 12761, score: 72, label: 'help wanted', language: 'Python' },
 { title: 'Detect duplicate import aliases', repo: 'astral-sh / ruff', number: 14388, score: 70, label: 'good first issue', language: 'Rust' },
];
export const pullRequests = [
 { title: 'fix: preserve timeout configuration on streaming requests', repo: 'encode / httpx', number: 3304, status: 'Merged', checks: '4 checks passed', changes: '+42 −8' },
 { title: 'feat: improve nested validation error messages', repo: 'pydantic / pydantic', number: 10861, status: 'In review', checks: '4 checks passed', changes: '+76 −12' },
 { title: 'docs: clarify optional query parameter behavior', repo: 'fastapi / fastapi', number: 12721, status: 'Merged', checks: '4 checks passed', changes: '+18 −5' },
];
export const pageMeta = (title: string, description: string) => ({ meta: [
 { title: `${title} — Patchwork` }, { name: 'description', content: description },
 { property: 'og:title', content: `${title} — Patchwork` }, { property: 'og:description', content: description },
 { property: 'og:type', content: 'website' }, { name: 'twitter:card', content: 'summary_large_image' },
] });
