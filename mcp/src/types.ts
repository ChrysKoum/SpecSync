/**
 * Response structure for git context tool
 */
export interface GitContextResponse {
  branch: string;           // Current branch name or commit SHA
  stagedFiles: string[];    // List of staged file paths
  diff: string;             // Full diff output from git diff --cached
  error?: string;           // Error message if git commands fail
}
