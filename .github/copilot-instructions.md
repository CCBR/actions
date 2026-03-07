---

# Reviewer guidance (what to look for in PRs)
- Reviewers MUST validate enforcement rules: no secrets, container specified, and reproducibility pins.
- If code is AI-generated, reviewers MUST ensure the author documents what was changed and why, and that the PR is labeled `generated-by-AI`.
- Reviewers SHOULD verify license headers and ownership metadata (for example, `CODEOWNERS`) are present.

---

# CI & enforcement suggestions (automatable)
1. **PR template**: include optional AI-assistance disclosure fields (model used, high-level prompt intent, manual review confirmation).
2. **Pre-merge check (GitHub Action)**: verify `.github/copilot-instructions.md` is present in the repository and that new pipeline files include a `# CRAFT:` header.
3. **Lint jobs**: `flake8`/`black` for Python, `shellcheck` for shell, and `nf-core lint` or Snakemake lint checks where applicable.
4. **Secrets scan**: run `TruffleHog` or `Gitleaks` on PRs to detect accidental credentials.
5. **AI usage label**: if AI usage is declared, an Action SHOULD add `generated-by-AI` label (create this label if it does not exist); the PR body SHOULD end with the italicized Markdown line: *Generated using AI*, and any associated commit messages SHOULD end with the plain footer line: `Generated using AI`.

_Sample GH Action check (concept): if AI usage is declared, require an AI-assistance disclosure field in the PR body._

---

# Security & compliance (mandatory)
- Developers MUST NOT send PHI or sensitive NIH internal identifiers to unapproved external AI services; use synthetic examples.
- Repository content MUST only be sent to model providers approved by NCI/NIH policy (for example, Copilot for Business or approved internal proxies).
- For AI-assisted actions, teams MUST keep an auditable record including: user, repository, action, timestamp, model name, and endpoint.
- If using a server wrapper (Option C), logs MUST include the minimum metadata above and follow institutional retention policy.
- If policy forbids external model use for internal code, teams MUST use approved local/internal LLM workflows.

---

# Operational notes (practical)
- `copilot-instructions.md` SHOULD remain concise and prescriptive; keep only high-value rules and edge-case examples.
- Developers SHOULD include the CRAFT block in edited files when requesting substantial generated code to improve context quality.

---

# Pipeline authoring guidance
- For Snakemake pipelines, authors MUST review existing CCBR pipelines first: <https://github.com/CCBR>.
- New pipelines SHOULD follow established CCBR conventions for folder layout, rule/process naming, config structure, and test patterns.
- For Nextflow pipelines, authors MUST follow nf-core patterns and references: <https://nf-co.re>.
- Nextflow code MUST use DSL2 only (DSL1 is not allowed).
- Pipelines MUST define container images and pin tool/image versions for reproducibility.
- Contributions SHOULD include a smoke test (small input) and a documented test command.
- For Nextflow, run `nf-core lint` (or equivalent checks) before PR submission.
- For Snakemake, run `snakemake --lint` and a dry-run before PR submission.

---

# Python and R script standards
- Python and R scripts MUST include module and function/class docstrings.
- Where a standard CLI framework is adopted, Python CLIs SHOULD use `typer` or `click` for consistency with existing components.
- R CLIs MUST use the `argparse` package.
- Scripts MUST support `--help` and document required/optional arguments.
- Python code MUST follow PEP 8, use `snake_case`, and include type hints for public functions.
- Scripts MUST return non-zero exit codes on failure and print clear error messages to stderr.
- Python code SHOULD pass `black`; R code SHOULD pass `lintr` and `styler`.
- Each script MUST include a documented smoke-test command in comments or README.

---

# AI-generated commit messages (Conventional Commits)
- Commit messages MUST follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) (as enforced in `CONTRIBUTING.md`).
- Generate messages from staged changes only (`git diff --staged`); do not include unrelated work.
- Commits SHOULD be atomic: one logical change per commit.
- If mixed changes are present, split into multiple logical commits; the number of commits does not need to equal the number of files changed.
- Subject format MUST be: `<type>(optional-scope): short imperative summary` (<=72 chars), e.g., `fix(profile): update release table parser`.
- Add a body only when needed to explain **why** and notable impact; never include secrets, tokens, PHI, or large diffs.
- For AI-assisted commits, add this final italicized footer line in the commit message body: *commit message is ai-generated*

Suggested prompt for AI tools:

```text
Create a Conventional Commit message from this staged diff.
Rules:
1) Use one of: feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert.
2) Keep subject <= 72 chars, imperative mood, no trailing period.
3) Include optional scope when clear.
4) Add a short body only if needed (why/impact), wrapped at ~72 chars.
5) Output only the final commit message.
```

---

# Onboarding checklist for new developers
- [ ] Read `.github/ai-agent-instructions.md` and CONTRIBUTING.md.  
- [ ] Configure VSCode workspace to open `ai-agent-instructions.md` by default (so Copilot Chat sees it).  

---

# Appendix: VSCode snippet (drop into `.vscode/snippets/craft.code-snippets`)
```json
{
  "Insert CRAFT prompt": {
    "prefix": "craft",
    "body": [
      "/* C: Context: Repo=${workspaceFolderBasename}; bioinformatics pipelines; NIH HPC (Biowulf/Helix); containers: quay.io/ccbr */",
      "/* R: Rules: no PHI, no secrets, containerize, pin versions, follow style */",
      "/* F: Flow: inputs/ -> results/, conf/, tests/ */",
      "/* T: Tests: provide a one-line TEST_CMD and expected output */",
      "",
      "A: $1"
    ],
    "description": "Insert CRAFT prompt and place cursor at Actions"
  }
}