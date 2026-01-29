# Commit Skill

Create a git commit for staged or all changes.

## Usage

```
/commit [message]
```

If no message is provided, generate one based on the changes.

## Instructions

1. Run `git status` to see current changes (never use `-uall` flag)
2. Run `git diff --staged` to see staged changes, and `git diff` for unstaged changes
3. If there are no staged changes but there are unstaged changes, ask the user if they want to stage all changes or select specific files
4. Analyze the changes and either:
   - Use the provided commit message, or
   - Generate a concise commit message following conventional commits format:
     - `feat:` for new features
     - `fix:` for bug fixes
     - `docs:` for documentation
     - `refactor:` for code refactoring
     - `chore:` for maintenance tasks
     - `test:` for adding tests
5. Create the commit with the message, adding co-author line:
   ```
   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
   ```
6. Run `git status` after commit to verify success

## Commit Message Guidelines

- Keep the subject line under 72 characters
- Use imperative mood ("add feature" not "added feature")
- Focus on **why** the change was made, not just what changed
- If the change is complex, add a body with more details

## Example

```bash
git commit -m "$(cat <<'EOF'
feat: add schema exploration tools for SYSPRO tables

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

## Safety

- Never use `--amend` unless explicitly requested
- Never use `--no-verify` unless explicitly requested
- Never commit files containing secrets (.env, credentials, etc.)
- Warn if committing large binary files
