#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { GitContextResponse } from "./types.js";
import { getStagedDiff } from "./git.js";
import { execSync } from "child_process";

/**
 * MCP Server for SpecSync - Git Context & Bridge Tools
 * Provides git repository context and cross-repo contract sync to Kiro
 */
class SpecSyncServer {
  private server: Server;

  constructor() {
    this.server = new Server(
      {
        name: "specsync",
        version: "1.1.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
  }

  private setupHandlers(): void {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: "git_get_staged_diff",
          description:
            "Get git context including current branch, staged files, and diff output. " +
            "Returns structured data about what changes are staged for commit.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "bridge_init",
          description:
            "Initialize SpecSync Bridge in the current repository. " +
            "Creates .kiro/settings/bridge.json and .kiro/contracts/ directory.",
          inputSchema: {
            type: "object",
            properties: {
              role: {
                type: "string",
                enum: ["consumer", "provider", "both"],
                description: "Role of this repository",
                default: "consumer",
              },
            },
            required: [],
          },
        },
        {
          name: "bridge_add_dependency",
          description:
            "Add a dependency to sync contracts from another repository.",
          inputSchema: {
            type: "object",
            properties: {
              name: {
                type: "string",
                description: "Name of the dependency (e.g., 'backend', 'auth-service')",
              },
              git_url: {
                type: "string",
                description: "Git repository URL",
              },
              contract_path: {
                type: "string",
                description: "Path to contract file in the dependency repo",
                default: ".kiro/contracts/provided-api.yaml",
              },
            },
            required: ["name", "git_url"],
          },
        },
        {
          name: "bridge_sync",
          description:
            "Sync contracts from dependencies. Fetches latest contracts via git.",
          inputSchema: {
            type: "object",
            properties: {
              dependency: {
                type: "string",
                description: "Specific dependency to sync (omit to sync all)",
              },
            },
            required: [],
          },
        },
        {
          name: "bridge_validate",
          description:
            "Validate API calls against cached contracts. Detects drift between " +
            "what your code calls and what the provider contract specifies.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "bridge_status",
          description:
            "Show status of Bridge configuration and all dependencies.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "bridge_extract",
          description:
            "Extract API contract from this repository's code. " +
            "Saves to .kiro/contracts/provided-api.yaml",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "bridge_detect",
          description:
            "Auto-detect if this repository is a provider (has API endpoints), " +
            "consumer (makes API calls), or both. Suggests the appropriate role.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
      ],
    }));

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      switch (name) {
        case "git_get_staged_diff": {
          const result: GitContextResponse = await getStagedDiff();
          return {
            content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
          };
        }

        case "bridge_init": {
          const role = (args as any)?.role || "consumer";
          return this.runBridgeCommand(`init --role ${role}`);
        }

        case "bridge_add_dependency": {
          const { name: depName, git_url, contract_path } = args as any;
          if (!depName || !git_url) {
            return {
              content: [{ type: "text", text: "Error: name and git_url are required" }],
              isError: true,
            };
          }
          const contractArg = contract_path ? `--contract-path "${contract_path}"` : "";
          return this.runBridgeCommand(`add-dependency ${depName} --git-url "${git_url}" ${contractArg}`);
        }

        case "bridge_sync": {
          const dep = (args as any)?.dependency || "";
          return this.runBridgeCommand(`sync ${dep}`);
        }

        case "bridge_validate": {
          return this.runBridgeCommand("validate");
        }

        case "bridge_status": {
          return this.runBridgeCommand("status");
        }

        case "bridge_extract": {
          return this.runBridgeCommand("extract");
        }

        case "bridge_detect": {
          return this.runBridgeCommand("detect");
        }

        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    });
  }

  private runBridgeCommand(command: string): { content: Array<{ type: string; text: string }>; isError?: boolean } {
    try {
      // Try specsync-bridge CLI first, fall back to python module
      let output: string;
      try {
        output = execSync(`specsync-bridge ${command}`, {
          encoding: "utf-8",
          timeout: 60000,
          cwd: process.cwd(),
        });
      } catch {
        // Fallback to python module
        output = execSync(`python -m specsync_bridge.cli ${command}`, {
          encoding: "utf-8",
          timeout: 60000,
          cwd: process.cwd(),
        });
      }
      return {
        content: [{ type: "text", text: output }],
      };
    } catch (error: any) {
      const errorOutput = error.stdout || error.stderr || error.message;
      return {
        content: [{ type: "text", text: `Error: ${errorOutput}` }],
        isError: true,
      };
    }
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("SpecSync MCP server running on stdio");
  }
}

// Start the server
const server = new SpecSyncServer();
server.run().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
