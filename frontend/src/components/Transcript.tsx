import { useLayoutEffect, useRef, useState } from "react";

import type { Turn as TurnModel } from "../state/transcript";
import { JumpToLatest } from "./JumpToLatest";
import { Turn } from "./Turn";

const NEAR_BOTTOM_PX = 80;

type Props = { turns: TurnModel[] };

export function Transcript({ turns }: Props): React.ReactElement {
  const listRef = useRef<HTMLUListElement>(null);
  const [awayFromBottom, setAwayFromBottom] = useState(false);

  useLayoutEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distance < NEAR_BOTTOM_PX) {
      el.scrollTop = el.scrollHeight;
    }
  }, [turns]);

  const onScroll = (): void => {
    const el = listRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAwayFromBottom(distance > NEAR_BOTTOM_PX);
  };

  const scrollToBottom = (): void => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setAwayFromBottom(false);
  };

  return (
    <div className="relative flex flex-1 flex-col">
      <ul
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
        onScroll={onScroll}
        className="flex flex-1 flex-col gap-3 overflow-y-auto pr-1"
      >
        {turns.map((t) => (
          <Turn key={t.id} turn={t} />
        ))}
      </ul>
      {awayFromBottom && <JumpToLatest onClick={scrollToBottom} />}
    </div>
  );
}
