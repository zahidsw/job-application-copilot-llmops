import { artifactDownloadUrl } from '../lib/api'
import { artifactLabel } from '../lib/format'
import type { GeneratedArtifact } from '../types'

interface ArtifactListProps {
  runId: string
  artifacts: GeneratedArtifact[]
}

export function ArtifactList({ runId, artifacts }: ArtifactListProps) {
  if (!artifacts.length) {
    return <p className="empty-state">No artifacts have been generated for this run yet.</p>
  }

  return (
    <div className="artifact-list">
      {artifacts.map((artifact) => (
        <article key={`${artifact.file_name}-${artifact.artifact_type}`} className="artifact-row">
          <div>
            <p className="artifact-label">{artifactLabel(artifact.artifact_type)}</p>
            <h4>{artifact.file_name}</h4>
          </div>
          <a
            className="ghost-button"
            href={artifactDownloadUrl(runId, artifact.file_name)}
            target="_blank"
            rel="noreferrer"
          >
            Open file
          </a>
        </article>
      ))}
    </div>
  )
}
