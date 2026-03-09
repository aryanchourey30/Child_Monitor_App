import type { RecentFrameViewModel } from "../types/api";

interface RecentFramesStripProps {
  frames: RecentFrameViewModel[];
  onSelect: (imageUrl: string) => void;
}

export function RecentFramesStrip({ frames, onSelect }: RecentFramesStripProps) {
  return (
    <section className="card">
      <h3>Recent Frames</h3>
      {frames.length === 0 ? (
        <p className="muted">No recent frames available.</p>
      ) : (
        <div className="thumb-strip">
          {frames.map((frame) => (
            <button
              key={`${frame.frameId}-${frame.timestamp ?? ""}`}
              className="thumb-btn"
              type="button"
              onClick={() => frame.frameUrl && onSelect(frame.frameUrl)}
              disabled={!frame.frameUrl}
            >
              {frame.frameUrl ? <img src={frame.frameUrl} alt={frame.frameId} /> : <span className="muted">No preview</span>}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
