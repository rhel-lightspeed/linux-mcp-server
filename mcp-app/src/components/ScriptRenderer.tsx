import { useState } from "react";
import type { ScriptType } from "../types";

/**
 * Maximum number of lines to display in the collapsed preview state.
 * If the script has more lines than this, a "Show all" toggle will be displayed.
 */
const PREVIEW_LINES = 5;

/**
 * ScriptRenderer - Displays a script with syntax highlighting and expandable preview
 *
 * This component renders a code block with the following features:
 * - Displays a language label (script type) in the top-right corner
 * - Shows a preview of the first PREVIEW_LINES lines by default for long scripts
 * - Provides a toggle to expand/collapse the full script content
 * - Automatically trims whitespace from the script
 *
 * @example
 * ```tsx
 * <ScriptRenderer
 *   script="#!/bin/bash\necho 'Hello World'\nls -la\npwd"
 *   scriptType="bash"
 * />
 * ```
 *
 * @param props - Component props
 * @param props.script - The script content to display. Will be trimmed of leading/trailing whitespace.
 * @param props.scriptType - The type of script (e.g., "bash", "python"). Displayed as a label and used for syntax context.
 *
 * @returns A rendered code block with optional expand/collapse functionality
 */
export function ScriptRenderer({
  script,
  scriptType,
}: {
  script: string;
  scriptType: ScriptType;
}) {
  const trimmedScript = script.trim();

  const [showFullScript, setShowFullScript] = useState<boolean>(false);
  const scriptLines = trimmedScript.split("\n");
  const hasMoreLines = scriptLines.length > PREVIEW_LINES;
  const displayScript = showFullScript
    ? trimmedScript
    : scriptLines.slice(0, PREVIEW_LINES).join("\n") +
      (hasMoreLines ? "\n..." : "");

  const hiddenLinesCount = scriptLines.length - PREVIEW_LINES;

  return (
    <div className="mb-4">
      <p className="text-sm mb-2">Commands to execute:</p>
      <div className="code-block">
        <div className="language-label">{scriptType}</div>
        <pre className="m-0">{displayScript}</pre>
      </div>
      {hasMoreLines && (
        <div className="mt-2">
          <a
            type="button"
            className="toggle-show-link"
            onClick={() => setShowFullScript((old) => !old)}
          >
            {showFullScript
              ? "Show less"
              : `Show all (${hiddenLinesCount} more lines)`}
          </a>
        </div>
      )}
    </div>
  );
}
