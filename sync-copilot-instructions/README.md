# sync-copilot-instructions

**`sync-copilot-instructions`** - Sync Copilot instructions from a
source repository to a target repository and open a PR

## Usage

### Basic example

[sync-copilot-instructions.yml](/examples/sync-copilot-instructions.yml)

```yaml
name: sync-copilot-instructions

on:
    schedule:
        - cron: "0 3 * * *"
    workflow_dispatch:
        inputs:
            source_repository:
                description: Source repository containing canonical Copilot instructions
                required: false
                default: CCBR/.github
                type: string
            source_ref:
                description: Branch, tag, or SHA to sync from
                required: false
                default: main
                type: string
            source_file:
                description: Path to canonical instructions file in source repository
                required: false
                default: .github/copilot-instructions.md
                type: string
            target_file:
                description: Path to destination instructions file in current repository
                required: false
                default: .github/copilot-instructions.md
                type: string
            commit_message:
                description: Commit message used when sync updates are detected
                required: false
                default: "chore: 🤖 sync copilot instructions"
                type: string

permissions:
    contents: write

concurrency:
    group: ${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: false

jobs:
    sync-copilot-instructions:
        runs-on: ubuntu-latest
        strategy:
            fail-fast: false
            matrix:
                OWNER: [CCBR]
                REPO:
                    - actions
                    - Tools
        steps:
            - uses: CCBR/actions/sync-copilot-instructions@latest
              with:
                  owner: ${{ matrix.OWNER }}
                  repo: ${{ matrix.REPO }}
                  app-id: ${{ vars.CCBR_BOT_APP_ID }}
                  app-private-key: ${{ secrets.CCBR_BOT_PRIVATE_KEY }}
                  source-repository: ${{ inputs.source_repository || github.event.inputs.source_repository || 'CCBR/.github' }}
                  source-ref: ${{ inputs.source_ref || github.event.inputs.source_ref || 'main' }}
                  source-file: ${{ inputs.source_file || github.event.inputs.source_file || '.github/copilot-instructions.md' }}
                  target-file: ${{ inputs.target_file || github.event.inputs.target_file || '.github/copilot-instructions.md' }}
                  commit-message: "${{ inputs.commit_message || github.event.inputs.commit_message || 'chore: 🤖 sync copilot instructions' }}"
```

## Inputs

- `owner`: Owner of the target repository. **Required.**
- `repo`: Name of the target repository. **Required.**
- `app-id`: GitHub App ID used to generate an installation token.
  **Required.**
- `app-private-key`: GitHub App private key used to generate an
  installation token. **Required.**
- `source-repository`: Source repository containing canonical Copilot
  instructions. **Required.** Default: `CCBR/.github`.
- `source-ref`: Branch, tag, or SHA in source repository. **Required.**
  Default: `main`.
- `source-file`: Path to canonical instructions file in source
  repository. **Required.** Default: `.github/copilot-instructions.md`.
- `target-file`: Path to destination instructions file in target
  repository. **Required.** Default: `.github/copilot-instructions.md`.
- `commit-message`: Commit message used when sync updates are detected.
  **Required.** Default: `chore: 🤖 sync copilot instructions`.
- `branch`: Branch name to use for the sync pull request. **Required.**
  Default: `update-copilot-instructions`.
