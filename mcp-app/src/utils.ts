import type {
  McpAppToolParams,
  ExecuteScriptResult,
  McpAppToolResult,
} from "./types";

import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";

export const formatOutput = (
  toolRequestParams: McpAppToolParams,
  toolResult: McpAppToolResult,
  executeScriptResult: ExecuteScriptResult,
) => {
  let result = "";

  if (toolRequestParams.script.trim().split("\n").length > 1) {
    result += `Script id=${toolResult.id} (${toolRequestParams.description}) executed`;
  } else {
    result += `Script \`${toolRequestParams.script}\` executed`;
  }

  if (executeScriptResult.state === "success") {
    result += " successfully, ";
  } else {
    result += ", ";
  }

  result += `and returned ${executeScriptResult.state}. Output:\n${executeScriptResult.output}`;
  return result;
};

export const formatOutputForToolError = (
  toolRequestParams: McpAppToolParams,
  toolResult: McpAppToolResult,
  message: string,
) => {
  return toolRequestParams.script.trim().split("\n").length > 1
    ? `Script id=${toolResult.id} (${toolRequestParams.description}) failed to execute: ${message}`
    : `Script \`${toolRequestParams.script}\` failed to execute: ${message}`;
};

/**
 * Extracts text content from a CallToolResult.
 *
 * @param callToolResult - The CallToolResult containing content to extract text from
 * @returns The extracted text string
 * @throws Runtime error if no text content is found in the content array
 */
export function extractText(callToolResult: CallToolResult): string {
  const { text } = callToolResult.content?.find((c) => c.type === "text")!;
  return text;
}
