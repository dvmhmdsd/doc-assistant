type Props = { onClick: () => void };

export function JumpToLatest({ onClick }: Props): React.ReactElement {
  return (
    <button
      type="button"
      onClick={onClick}
      className="sticky bottom-4 self-center rounded-full bg-blue-600 px-3 py-1 text-xs text-white shadow-lg hover:bg-blue-500 focus-visible:ring-2 focus-visible:ring-blue-300"
    >
      Jump to latest ↓
    </button>
  );
}
