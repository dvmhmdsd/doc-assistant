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
      <div className="mb-1 flex items-baseline gap-2 text-xs text-neutral-400">
        <span
          className={clsx(
            "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
            isUser ? "bg-blue-500/30 text-blue-100" : "bg-neutral-700/60 text-neutral-200",
          )}
        >
          {isUser ? "You" : "Assistant"}
        </span>
        {turn.state === "stopped" && <span className="text-amber-400">stopped</span>}
        {turn.state === "errored" && <span className="text-red-400">errored</span>}
        <time dateTime={turn.createdAt} className="ml-auto text-neutral-500">
          {new Date(turn.createdAt).toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
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
