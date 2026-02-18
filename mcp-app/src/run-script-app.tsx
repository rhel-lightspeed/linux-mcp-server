import type { App, McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import {
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
  useApp,
} from "@modelcontextprotocol/ext-apps/react";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ExecuteScriptResultSchema,
  McpAppToolParamsSchema,
  McpAppToolResultSchema,
  type ExecutionState,
} from "./types";
import { formatOutput, formatOutputForToolError } from "./utils";

const IMPLEMENTATION = { name: "Run Script App", version: "1.0.0" };

const log = {
  info: console.log.bind(console, "[APP]"),
  warn: console.warn.bind(console, "[APP]"),
  error: console.error.bind(console, "[APP]"),
};

function RunScriptApp() {
  const [toolResult, setToolResult] = useState<CallToolResult | undefined>(
    undefined,
  );
  const [toolRequestParams, setToolRequestParams] = useState<
    Record<string, unknown> | undefined
  >(undefined);
  const [hostContext, setHostContext] = useState<McpUiHostContext>();

  const { app, error } = useApp({
    appInfo: IMPLEMENTATION,
    capabilities: {},
    onAppCreated: (app) => {
      app.onteardown = async () => {
        log.info("App is being torn down");
        return {};
      };
      app.ontoolinput = async (input) => {
        const { arguments: args } = input;
        log.info("Received tool call input:", input);
        setToolRequestParams(args);
      };

      app.ontoolresult = async (result) => {
        log.info("Received tool call result:", result);
        setToolResult(result);
      };

      app.onhostcontextchanged = (ctx) => {
        setHostContext((prev) => ({ ...prev, ...ctx }));
      };

      app.onerror = log.error;
    },
  });

  // Set initial host context after connection
  useEffect(() => {
    if (app) {
      setHostContext(app.getHostContext());
    }
  }, [app]);

  useEffect(() => {
    if (hostContext?.theme) {
      applyDocumentTheme(hostContext.theme);
    }
    if (hostContext?.styles?.variables) {
      applyHostStyleVariables(hostContext.styles.variables);
    }
    if (hostContext?.styles?.css?.fonts) {
      applyHostFonts(hostContext.styles.css.fonts);
    }
  }, [hostContext]);

  if (error)
    return (
      <div>
        <strong>ERROR:</strong> {error.message}
      </div>
    );
  if (!app) return <div>Connecting...</div>;

  return (
    <RunScriptAppInner
      app={app}
      toolRequestParams={toolRequestParams}
      toolResult={toolResult}
    />
  );
}

interface RunScriptAppInnerProps {
  app: App;
  toolRequestParams: Record<string, unknown> | undefined;
  toolResult: CallToolResult | undefined;
}

// TODO: This function would be deleted in the following UI rework PR
const pickStateColor = (state: ExecutionState): string => {
  switch (state) {
    case "initial":
    case "waiting-approval":
      return "text-white";
    case "executing":
      return "text-yellow-500";
    case "success":
      return "text-green-500";
    default:
      return "text-red-500";
  }
};

function RunScriptAppInner({
  app,
  toolRequestParams,
  toolResult,
}: RunScriptAppInnerProps) {
  const [executionState, setExecutionState] =
    useState<ExecutionState>("initial");
  const [executionResult, setExecutionResult] = useState<string>("");

  const validatedToolRequestParams = useMemo(() => {
    const parsedResult = McpAppToolParamsSchema.safeParse(toolRequestParams);
    return parsedResult.success ? parsedResult.data : undefined;
  }, [toolRequestParams]);

  const validatedToolResult = useMemo(() => {
    const parsedResult = McpAppToolResultSchema.safeParse(
      toolResult?.structuredContent,
    );

    return parsedResult.success ? parsedResult.data : undefined;
  }, [toolResult]);

  useEffect(() => {
    if (!validatedToolResult) return;

    const getExecutionStateFromServer = async () => {
      const result = await app.callServerTool({
        name: "get_execution_state",
        arguments: {
          id: validatedToolResult.id,
        },
      });

      if (!result.isError && result.structuredContent) {
        setExecutionState(result.structuredContent.state as ExecutionState);
        return result.structuredContent.state;
      }
    };

    getExecutionStateFromServer();
  }, [app, validatedToolResult]);

  const handleAccept = async () => {
    if (!validatedToolRequestParams || !validatedToolResult) return;

    setExecutionState("executing");

    let updatedExecutionState: ExecutionState = executionState;
    let updatedExecutionResult = executionResult;
    let outputToModel = "";

    try {
      const result = await app.callServerTool({
        name: "execute_script",
        arguments: { id: validatedToolResult.id },
      });

      const executeScriptResult = ExecuteScriptResultSchema.parse(
        result.structuredContent,
      );

      updatedExecutionResult = executeScriptResult.output;
      updatedExecutionState = executeScriptResult.state;

      outputToModel = formatOutput(
        validatedToolRequestParams,
        validatedToolResult,
        executeScriptResult,
      );
    } catch (e) {
      outputToModel = formatOutputForToolError(
        validatedToolRequestParams,
        validatedToolResult,
        JSON.stringify(e),
      );

      updatedExecutionState = "failure";
      updatedExecutionResult = JSON.stringify(e);
    }

    setExecutionState(updatedExecutionState);
    setExecutionResult(updatedExecutionResult);

    app.sendMessage({
      role: "user",
      content: [
        {
          type: "text",
          text: outputToModel,
        },
      ],
    });
  };

  const handleReject = async () => {
    if (!validatedToolResult) return;

    setExecutionState("rejected-user");
    app.callServerTool({
      name: "reject_script",
      arguments: { id: validatedToolResult.id },
    });
  };

  if (!validatedToolResult || !validatedToolRequestParams) {
    return (
      <div className="flex justify-center items-center min-h-[200px]">
        <div className="flex items-center">
          <span className="relative flex size-3 mr-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-yellow-400 opacity-75"></span>
            <span className="relative inline-flex size-3 rounded-full bg-yellow-500"></span>
          </span>
          <span>Waiting for the detail information...</span>
        </div>
      </div>
    );
  }

  switch (validatedToolResult.status) {
    case "OK":
      return (
        <div className="p-2">
          <div className="flex">
            <div className="flex-1 whitespace-pre-wrap break-all">
              <p>
                <strong>Execution State:</strong>{" "}
                <span className={pickStateColor(executionState)}>
                  {executionState}
                </span>
              </p>
              <p>
                <strong>Script:</strong> {validatedToolRequestParams.script}
              </p>
              <p>
                <strong>Script Type:</strong>{" "}
                {validatedToolRequestParams.scriptType}
              </p>
              <p>
                <strong>Description:</strong>{" "}
                {validatedToolRequestParams.description}
              </p>
              {executionResult !== null && (
                <p>
                  <strong>Result:</strong> {executionResult}
                </p>
              )}
            </div>
            <div className="flex-none">
              <button
                className="btn-primary"
                disabled={executionState !== "waiting-approval"}
                onClick={handleAccept}
              >
                Allow
              </button>
              <button
                className="btn-primary"
                disabled={executionState !== "waiting-approval"}
                onClick={handleReject}
              >
                Deny
              </button>
            </div>
          </div>
        </div>
      );
    default:
      return (
        <div className="p-2 whitespace-pre-wrap break-all">
          <p>
            <strong>Gatekeeper State:</strong>{" "}
            <span className="text-red-500">{validatedToolResult.status}</span>
          </p>
          <p>
            <strong>Detail:</strong> <span>{validatedToolResult.detail}</span>
          </p>
        </div>
      );
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RunScriptApp />
  </StrictMode>,
);
