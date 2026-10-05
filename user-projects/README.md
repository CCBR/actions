# user-projects

**`user-projects`** - Add issue/PR to user’s project

Automatically add issues and pull requests to a user’s GitHub project
board. This action maps assignees to project boards using a YAML
configuration file and supports both token-based and GitHub App
authentication for enhanced security.

## Usage

The action reads a YAML file that maps GitHub usernames to project board
URLs. When an issue or PR is assigned to a user, the action
automatically adds it to their corresponding project board.

### Basic example with GitHub token

```yaml
steps:
  - uses: CCBR/actions/user-projects@main
    with:
      github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Example with GitHub App authentication

For enhanced security, you can use a GitHub App instead of a personal
access token. Create a GitHub App with the necessary permissions and
store the Client ID and private key as organization variables or
secrets.

```yaml
steps:
  - uses: CCBR/actions/user-projects@main
    with:
      client-id: ${{ vars.CCBR_BOT_CLIENT_ID }}
      app-private-key: ${{ secrets.CCBR_BOT_PRIVATE_KEY }}
      token-owner: CCBR
```

For a complete example workflow, see
[user-projects.yml](./examples/user-projects.yml).

## Inputs

- `username`: GitHub username of the person assigned to the Issue or PR.
  Default: `${{ github.event.assignee.login }}`.
- `user_projects`: URL of a yaml file mapping usernames to project
  boards. Default:
  `https://raw.githubusercontent.com/CCBR/.github/main/assets/user-kanbans.yml`.
- `github-token`: GitHub Actions token with access to organization
  projects. Optional - set the client-id and app-private-key instead.
- `client-id`: GitHub App Client ID for authentication. Optional - use
  this instead of a token.
- `app-id`: Legacy GitHub App ID input. Prefer client-id.
- `app-private-key`: Private key for the GitHub App used for
  authentication. Optional - must be set if client-id or app-id is set.
- `token-owner`: Owner of the resources that the GitHub app will use for
  authentication. Optional - use this if using client-id or app-id and
  app-private-key. Default: `CCBR`.
