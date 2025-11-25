#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { GitContextResponse } from "./types.js";
import { getStagedDiff } from "./git.js";

/**
 * MCP Server for SpecSync Git Context Tool
 * Provides git repository context to Kiro for validation
 */
class GitContextServer {
  private server: Server;

  constructor() {
    this.server = new Server(
      {
        name: "specsync-git-context",
        version: "1.0.0",
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
          name: "get_staged_diff",
          description:
            "Get git context including current branch, staged files, and diff output. " +
            "Returns structured data about what changes are staged for commit.",
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
      if (request.params.name === "get_staged_diff") {
        const result: GitContextResponse = await getStagedDiff();
        
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      throw new Error(`Unknown tool: ${request.params.name}`);
    });
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("SpecSync Git Context MCP server running on stdio");
  }
}

// Start the server
const server = new GitContextServer();
server.run().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
