import type { Citation } from "../api/generated";

type Props = { citations: Citation[] };

export function CitationList({ citations }: Props): React.ReactElement | null {
  if (citations.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-wrap gap-2 text-xs text-neutral-400">
      {citations.map((c) => (
        <li
          key={c.chunk_id}
          className="rounded border border-neutral-700 bg-neutral-800/40 px-2 py-1"
        >
          {c.locator}
          <span className="ml-1 text-neutral-500">({c.score.toFixed(1)})</span>
        </li>
      ))}
    </ul>
  );
}
