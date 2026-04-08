import type { ExecutionState, McpAppToolResult } from "../types";

/**
 * Renders action buttons for script execution approval
 * @param executionState - Current state of script execution
 * @param mcpAppToolResult - Result from the MCP app tool
 * @param handleAccept - Callback when user approves execution
 * @param handleReject - Callback when user denies execution
 */
export function ScriptAction({
  executionState,
  mcpAppToolResult,
  handleAccept,
  handleReject,
}: {
  executionState: ExecutionState;
  mcpAppToolResult: McpAppToolResult;
  handleAccept: () => Promise<void>;
  handleReject: () => Promise<void>;
}) {
  switch (executionState) {
    case "initial":
    case "waiting-approval":
      return (
        <>
          <button
            className="btn-primary"
            disabled={executionState !== "waiting-approval"}
            onClick={handleAccept}
          >
            Allow
          </button>
          <button
            className="btn-secondary"
            disabled={executionState !== "waiting-approval"}
            onClick={handleReject}
          >
            Deny
          </button>
        </>
      );
    case "success":
    case "failure":
    case "executing":
      return <div className="status-allowed">Allowed</div>;
    case "rejected-user":
      return <div className="status-rejected">Denied</div>;
    case "rejected-gatekeeper":
      return (
        <div className="status-rejected">
          Automatically rejected: {mcpAppToolResult.detail}
        </div>
      );
  }
}
