import { exec } from "child_process";
import { promisify } from "util";
import { GitContextResponse } from "./types.js";

const execAsync = promisify(exec);

/**
 * Execute a git command and return stdout
 * Throws descriptive errors for common failure scenarios
 */
async function executeGitCommand(command: string): Promise<string> {
  try {
    const { stdout } = await execAsync(command, {
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer for large diffs
    });
    return stdout.trim();
  } catch (error: any) {
    const stderr = error.stderr || "";
    const message = error.message || "";
    
    // Check for non-git directory
    if (stderr.includes("not a git repository") || message.includes("not a git repository")) {
      throw new Error("Not a git repository. Please run this command from within a git repository.");
    }
    
    // Check for permission errors
    if (stderr.includes("Permission denied") || message.includes("Permission denied")) {
      throw new Error("Permission denied. Check file permissions for the git repository.");
    }
    
    // Generic error
    throw new Error(`Git command failed: ${stderr || message}`);
  }
}

/**
 * Get the current branch name or commit SHA if in detached HEAD state
 */
async function getCurrentBranch(): Promise<string> {
  const branch = await executeGitCommand("git rev-parse --abbrev-ref HEAD");
  
  // If in detached HEAD state, git returns "HEAD"
  if (branch === "HEAD") {
    // Get the commit SHA instead
    const commitSha = await executeGitCommand("git rev-parse HEAD");
    return commitSha;
  }
  
  return branch;
}

/**
 * Get list of staged files
 * Returns empty array if no files are staged
 */
async function getStagedFiles(): Promise<string[]> {
  const output = await executeGitCommand("git diff --cached --name-only");
  
  // If no files are staged, return empty array
  if (!output) {
    return [];
  }
  
  return output.split("\n").filter((file) => file.length > 0);
}

/**
 * Get the diff of staged changes
 * Returns empty string if no changes are staged
 */
async function getStagedDiffContent(): Promise<string> {
  const diff = await executeGitCommand("git diff --cached");
  return diff;
}

/**
 * Main function to get all git context
 * Returns structured git context including branch, staged files, and diff
 */
export async function getStagedDiff(): Promise<GitContextResponse> {
  try {
    const [branch, stagedFiles, diff] = await Promise.all([
      getCurrentBranch(),
      getStagedFiles(),
      getStagedDiffContent(),
    ]);

    return {
      branch,
      stagedFiles,
      diff,
    };
  } catch (error) {
    // Return error in structured format
    return {
      branch: "",
      stagedFiles: [],
      diff: "",
      error: (error as Error).message,
    };
  }
}
