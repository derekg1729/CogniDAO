import {
  Request as MCPRequest,
  ServerResult as MCPResponse,
} from "@modelcontextprotocol/sdk/types.js";
import { Controller } from "../../../../presentation/protocols/controller.js";
import { serializeError } from "../helpers/serialize-error.js";
import { MCPRequestHandler } from "./mcp-router-adapter.js";

export const adaptMcpRequestHandler = async <
  T extends any,
  R extends Error | any
>(
  controller: Controller<T, R>
): Promise<MCPRequestHandler> => {
  return async (request: MCPRequest): Promise<MCPResponse> => {
    const { params } = request;
    const body = params?.arguments as T;
    const response = await controller.handle({
      body,
    });

    const isError = response.statusCode < 200 || response.statusCode >= 300;

    return {
      tools: [],
      isError,
      content: [
        {
          type: "text",
          text: isError
            ? JSON.stringify(serializeError(response.body))
            : response.body?.toString(),
        },
      ],
    };
  };
};
