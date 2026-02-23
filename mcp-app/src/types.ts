import { z } from "zod";

export const McpAppToolParamsSchema = z
  .object({
    script: z.string(),
    script_type: z.enum(["bash", "python"]),
    description: z.string(),
    host: z.string().optional().nullable(),
  })
  .transform((data) => ({
    script: data.script,
    scriptType: data.script_type,
    description: data.description,
    host: data.host,
  }));

export type McpAppToolParams = z.infer<typeof McpAppToolParamsSchema>;

export const ExecuteScriptResultSchema = z.object({
  state: z.enum(["success", "failure"]),
  output: z.string(),
});

export type ExecuteScriptResult = z.infer<typeof ExecuteScriptResultSchema>;

export const McpAppToolResultSchema = z.object({
  status: z.enum([
    "OK",
    "BAD_DESCRIPTION",
    "POLICY",
    "MODIFIES_SYSTEM",
    "UNCLEAR",
    "DANGEROUS",
    "MALICIOUS",
  ]),
  detail: z.string(),
  id: z.string(),
});

export type McpAppToolResult = z.infer<typeof McpAppToolResultSchema>;

const executionState = [
  "initial",
  "success",
  "failure",
  "rejected-user",
  "rejected-gatekeeper",
  "waiting-approval",
  "executing",
] as const;

const ExecutionStateSchema = z.enum(executionState);

export type ExecutionState = z.infer<typeof ExecutionStateSchema>;

export const GetExecutionStateResultSchema = z.object({
  state: ExecutionStateSchema,
});

export type GetExecutionStateResult = z.infer<
  typeof GetExecutionStateResultSchema
>;
