import { useRef, useState } from 'react'

interface UploadPanelProps {
  isUploading: boolean
  uploadProgress: number
  uploadingFilename: string | null
  onUpload: (file: File) => Promise<boolean>
}

const ACCEPTED_TYPES = '.pdf,.docx,.txt'
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'txt'])

export function UploadPanel({
  isUploading,
  uploadProgress,
  uploadingFilename,
  onUpload,
}: UploadPanelProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function chooseFile(file: File | undefined) {
    setError(null)
    if (!file) return

    const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ALLOWED_EXTENSIONS.has(extension)) {
      setSelectedFile(null)
      setError('Choose a PDF, DOCX, or TXT file.')
      if (inputRef.current) inputRef.current.value = ''
      return
    }

    setSelectedFile(file)
  }

  async function submitUpload() {
    if (!selectedFile || isUploading) return
    const didUpload = await onUpload(selectedFile)
    if (didUpload) {
      setSelectedFile(null)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <section className="upload-section" aria-labelledby="upload-documents-title">
      <div className="sidebar-section-heading">
        <div>
          <h2 id="upload-documents-title">Add documents</h2>
          <p>PDF, DOCX, or TXT files</p>
        </div>
        <span className="upload-heading-icon" aria-hidden="true">
          <svg viewBox="0 0 20 20">
            <path d="M10 13V3m0 0L6.5 6.5M10 3l3.5 3.5M4 12v4h12v-4" />
          </svg>
        </span>
      </div>

      <div
        className={`upload-dropzone ${isDragging ? 'upload-dropzone--dragging' : ''} ${selectedFile ? 'upload-dropzone--selected' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          if (!isUploading) setIsDragging(true)
        }}
        onDragLeave={(event) => {
          if (
            !(event.relatedTarget instanceof Node) ||
            !event.currentTarget.contains(event.relatedTarget)
          ) {
            setIsDragging(false)
          }
        }}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragging(false)
          chooseFile(event.dataTransfer.files[0])
        }}
      >
        <input
          ref={inputRef}
          id="knowledge-file-input"
          className="sr-only"
          type="file"
          accept={ACCEPTED_TYPES}
          disabled={isUploading}
          onChange={(event) => chooseFile(event.target.files?.[0])}
        />
        <span className="upload-drop-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M12 15V4m0 0L8 8m4-4 4 4M5 14v5h14v-5" />
          </svg>
        </span>
        <p>
          {selectedFile ? (
            <strong title={selectedFile.name}>{selectedFile.name}</strong>
          ) : (
            <>
              <label htmlFor="knowledge-file-input">Choose file</label>
              <span> or drop it here</span>
            </>
          )}
        </p>
        {selectedFile && (
          <span className="selected-file-size">
            {(selectedFile.size / 1024).toFixed(1)} KB
          </span>
        )}
      </div>

      <button
        className="sidebar-upload-button"
        type="button"
        disabled={!selectedFile || isUploading}
        onClick={submitUpload}
      >
        {isUploading ? 'Uploading…' : 'Upload document'}
      </button>

      {isUploading && uploadingFilename && (
        <div className="sidebar-upload-progress" role="status" aria-live="polite">
          <div className="upload-progress-label">
            <span title={uploadingFilename}>{uploadingFilename}</span>
            <span>{uploadProgress}%</span>
          </div>
          <div
            className="upload-progress-track"
            role="progressbar"
            aria-label="Upload progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={uploadProgress}
          >
            <span style={{ width: `${uploadProgress}%` }} />
          </div>
        </div>
      )}

      {error && (
        <p className="upload-inline-error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
