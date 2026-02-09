import type { App, McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import {
  applyDocumentTheme,
  applyHostFonts,
  applyHostStyleVariables,
  useApp,
} from "@modelcontextprotocol/ext-apps/react";
import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

const IMPLEMENTATION = { name: "Run Script App", version: "1.0.0" };

type GateKeeperStatus =
  | "OK"
  | "BAD_DESCRIPTION"
  | "POLICY"
  | "MODIFIES_SYSTEM"
  | "UNCLEAR"
  | "DANGEROUS"
  | "MALICIOUS";

const log = {
  info: console.log.bind(console, "[APP]"),
  warn: console.warn.bind(console, "[APP]"),
  error: console.error.bind(console, "[APP]"),
};

function extractText(callToolResult: CallToolResult): string {
  const { text } = callToolResult.content?.find((c) => c.type === "text")!;
  return text;
}

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

type ExecutionState =
  | "initialized"
  | "success"
  | "failed"
  | "rejected"
  | "executing";

const pickStateColor = (state: ExecutionState): string => {
  switch (state) {
    case "initialized":
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
    useState<ExecutionState>("initialized");
  const [executionResult, setExecutionResult] = useState<string>("");

  const handleAccept = useCallback(async () => {
    setExecutionState("executing");

    const params = toolRequestParams || {};
    const script = (params["script"] || "") as string;
    const scriptType = (params["script_type"] || "bash") as string;
    const host = params["host"] || null;

    let updatedExecutionState: ExecutionState = executionState;
    let updatedExecutionResult = executionResult;

    try {
      const result = await app.callServerTool({
        name: "execute_script",
        arguments: { script: script, script_type: scriptType, host: host },
      });

      if (!!result.isError) {
        updatedExecutionState = "failed";
      } else {
        updatedExecutionState = "success";
      }

      updatedExecutionResult = extractText(result);
    } catch (e) {
      updatedExecutionState = "failed";
      updatedExecutionResult = e as string;
      console.error("callServerTool failed", e);
    }

    setExecutionState(updatedExecutionState);
    setExecutionResult(updatedExecutionResult);

    try {
      await app.sendMessage({
        role: "user",
        content: [
          {
            type: "text",
            text: `The script ${script} has been executed. Here is the detail of the execution.\n--------------------------------------------\nExecution status: ${updatedExecutionState}\nExecution result: ${updatedExecutionResult}`,
          },
        ],
      });
    } catch (e) {
      console.error(`sendMessage failed: ${e}`);
    }
  }, [app, toolRequestParams]);

  const handleReject = () => {
    setExecutionState("rejected");
  };

  if (!toolResult || !toolRequestParams) {
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

  switch (toolResult.structuredContent!["status"] as GateKeeperStatus) {
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
                <strong>Script:</strong> {toolRequestParams["script"] as string}
              </p>
              <p>
                <strong>Script Type:</strong>{" "}
                {toolRequestParams["script_type"] as string}
              </p>
              <p>
                <strong>Description:</strong>{" "}
                {toolRequestParams["description"] as string}
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
                disabled={executionState !== "initialized"}
                onClick={handleAccept}
              >
                Allow
              </button>
              <button
                className="btn-primary"
                disabled={executionState !== "initialized"}
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
            <span className="text-red-500">
              {toolResult.structuredContent!["status"] as string}
            </span>
          </p>
          <p>
            <strong>Detail:</strong>{" "}
            <span>{toolResult.structuredContent!["detail"] as string}</span>
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
