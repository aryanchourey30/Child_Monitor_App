import { formatDateTime } from "../utils/format";

interface LatestFramePanelProps {
  imagePath?: string | null;
  timestamp?: string | null;
  selectedImage?: string | null;
}

export function LatestFramePanel({ imagePath, timestamp, selectedImage }: LatestFramePanelProps) {
  const effectiveImage = selectedImage || imagePath;

  return (
    <section className="card latest-frame">
      <h3>Latest Frame</h3>
      {effectiveImage ? (
        <img alt="Latest frame" src={effectiveImage} className="frame-image" />
      ) : (
        <div className="empty-placeholder">No frame available</div>
      )}
      <p className="muted">Last frame: {formatDateTime(timestamp)}</p>
    </section>
  );
}
