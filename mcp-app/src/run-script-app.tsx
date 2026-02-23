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
  GetExecutionStateResultSchema,
  McpAppToolParamsSchema,
  McpAppToolResultSchema,
  type ExecutionState,
} from "./types";
import {
  extractText,
  formatExecutionState,
  formatOutput,
  formatOutputForToolError,
} from "./utils";
import { ScriptRenderer } from "./components/ScriptRenderer";
import { ScriptAction } from "./components/ScriptAction";

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

function RunScriptAppInner({
  app,
  toolRequestParams,
  toolResult,
}: RunScriptAppInnerProps) {
  const [executionState, setExecutionState] =
    useState<ExecutionState>("initial");
  const [executionResult, setExecutionResult] = useState<string>("");

  const validatedToolRequestParams = useMemo(() => {
    if (!toolRequestParams) {
      return undefined;
    }

    const parsedResult = McpAppToolParamsSchema.safeParse(toolRequestParams);

    if (parsedResult.success) {
      return parsedResult.data;
    } else {
      log.error(parsedResult.error);
      return undefined;
    }
  }, [toolRequestParams]);

  const validatedToolResult = useMemo(() => {
    if (!toolResult) {
      return undefined;
    }

    const parsedResult = McpAppToolResultSchema.safeParse(
      toolResult?.structuredContent,
    );

    if (parsedResult.success) {
      return parsedResult.data;
    } else {
      log.error(parsedResult.error);
      return undefined;
    }
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

      if (result.isError) return;

      const validatedResult = GetExecutionStateResultSchema.safeParse(
        result.structuredContent,
      );

      if (validatedResult.success) {
        setExecutionState(validatedResult.data.state);
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

      if (result.isError) {
        throw new Error(extractText(result));
      }

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

  return (
    <div className="p-2">
      <div className="p-4 border rounded-2xl mb-2">
        <div className="mb-4">
          {/* TODO: we can dynamically inject the platform that users are using here */}
          <p className="text-base">
            Goose wants to perform the following action on{" "}
            <strong>{validatedToolRequestParams.host || "localhost"}</strong>
          </p>
        </div>

        <div className="description-box">
          {validatedToolRequestParams.description}
        </div>

        <ScriptRenderer
          script={validatedToolRequestParams.script}
          scriptType={validatedToolRequestParams.scriptType}
        />

        <div className="flex justify-end gap-2">
          <ScriptAction
            executionState={executionState}
            mcpAppToolResult={validatedToolResult}
            handleAccept={handleAccept}
            handleReject={handleReject}
          />
        </div>
      </div>

      <div className="border rounded-md w-fit px-2 text-sm">
        {formatExecutionState(executionState)}
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RunScriptApp />
  </StrictMode>,
);
