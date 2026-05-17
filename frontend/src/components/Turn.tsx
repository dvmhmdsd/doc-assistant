import clsx from "clsx";

import type { Turn as TurnModel } from "../state/transcript";
import { CitationList } from "./CitationList";

type Props = { turn: TurnModel };

export function Turn({ turn }: Props): React.ReactElement {
  const isUser = turn.role === "user";
  const streaming = turn.state === "streaming";

  return (
    <li
      data-role={turn.role}
      data-state={turn.state}
      data-streaming={streaming ? "true" : "false"}
      className={clsx(
        "rounded-lg px-3 py-2 text-sm",
        isUser
          ? "self-end bg-blue-600/30 text-blue-50"
          : "self-start bg-neutral-800/60 text-neutral-100",
      )}
    >
      <div className="mb-1 text-xs uppercase tracking-wide text-neutral-400">
        {isUser ? "You" : "Assistant"}
        {turn.state === "stopped" && <span className="ml-2 text-amber-400">stopped</span>}
        {turn.state === "errored" && <span className="ml-2 text-red-400">errored</span>}
      </div>
      <p
        data-testid={streaming ? "turn-streaming-text" : undefined}
        className="whitespace-pre-wrap break-words"
      >
        {turn.content}
      </p>
      {turn.citations && turn.citations.length > 0 && (
        <CitationList citations={turn.citations} />
      )}
    </li>
  );
}
