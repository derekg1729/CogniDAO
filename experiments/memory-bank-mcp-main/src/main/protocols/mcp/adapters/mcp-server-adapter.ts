import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
  ServerResult as MCPResponse,
} from "@modelcontextprotocol/sdk/types.js";
import { McpRouterAdapter } from "./mcp-router-adapter.js";

export class McpServerAdapter {
  private server: Server | null = null;

  constructor(private readonly mcpRouter: McpRouterAdapter) {}

  public register({ name, version }: { name: string; version: string }) {
    this.server = new Server(
      {
        name,
        version,
      },
      {
        capabilities: {
          tools: this.mcpRouter.getToolCapabilities(),
        },
      }
    );

    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: this.mcpRouter.getToolsSchemas(),
    }));

    this.server.setRequestHandler(
      CallToolRequestSchema,
      async (request): Promise<MCPResponse> => {
        const { name } = request.params;
        const handler = await this.mcpRouter.getToolHandler(name);
        if (!handler) {
          throw new McpError(
            ErrorCode.MethodNotFound,
            `Tool ${name} not found`
          );
        }
        return await handler(request);
      }
    );
  }

  async start(): Promise<void> {
    if (!this.server) {
      throw new Error("Server not initialized");
    }

    const transport = new StdioServerTransport();
    try {
      await this.server.connect(transport);
      console.log("Memory Bank MCP server running on stdio");
    } catch (error) {
      console.error(error);
    }
  }
}
