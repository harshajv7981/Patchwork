<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Frontend architecture
- Keep the contribution workspace in a shared browser-safe component with individual TanStack leaf routes for each view, so navigation and page metadata remain independently addressable.
- Keep demonstration data separate from the workspace and label disconnected services explicitly; frontend previews must not imply real GitHub or AI operations.
- Define visual roles in the global CSS design system and use the shared UI controls to maintain consistent styling.
