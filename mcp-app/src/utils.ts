import type {
  McpAppToolParams,
  ExecuteScriptResult,
  McpAppToolResult,
} from "./types";

export const formatOutput = (
  toolRequestParams: McpAppToolParams,
  toolResult: McpAppToolResult,
  executeScriptResult: ExecuteScriptResult,
) => {
  let result = "";

  if (toolRequestParams.script.trim().split("\n").length > 1) {
    result += `Script ${toolResult.id} ${toolRequestParams.description} executed`;
  } else {
    result += `Script ${toolRequestParams.script} executed`;
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
    ? `Script ${toolResult.id} ${toolRequestParams.description} failed to execute: ${message}`
    : `Script ${toolRequestParams.script} failed to execute: ${message}`;
};
