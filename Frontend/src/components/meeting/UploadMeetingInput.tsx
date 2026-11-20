import React, { useRef, useState } from 'react';
import { UploadCloud, FileAudio, X } from 'lucide-react';
import { Button } from '../common/Button';
import { APP_CONFIG } from '../../constants/appConstants';
import { formatBytes } from '../../utils/formatters';

interface UploadMeetingInputProps {
  onUpload: (file: File) => Promise<void>;
  isLoading?: boolean;
}

export const UploadMeetingInput: React.FC<UploadMeetingInputProps> = ({
  onUpload,
  isLoading = false,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const maxBytes = APP_CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024;
      if (file.size > maxBytes) {
        setError(`File is too large. Maximum size is ${APP_CONFIG.MAX_FILE_SIZE_MB}MB.`);
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setError(null);
  };

  const handleUploadSubmit = async () => {
    if (!selectedFile) {
      fileInputRef.current?.click();
      return;
    }

    try {
      await onUpload(selectedFile);
      handleClear();
    } catch (err: unknown) {
      setError((err as Error)?.message || 'Upload failed.');
    }
  };

  return (
    <div className="w-full">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept={APP_CONFIG.ACCEPTED_AUDIO_VIDEO_TYPES}
        className="hidden"
      />

      {selectedFile ? (
        <div className="flex items-center justify-between p-2.5 bg-indigo-50/70 border border-indigo-200 rounded-lg min-w-0">
          <div className="flex items-center gap-2.5 min-w-0 pr-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
              <FileAudio className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-indigo-950 truncate">{selectedFile.name}</p>
              <p className="text-[11px] text-indigo-600">{formatBytes(selectedFile.size)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleClear}
              className="p-1 text-slate-400 hover:text-slate-600 rounded"
              disabled={isLoading}
              aria-label="Remove file"
            >
              <X className="w-4 h-4" />
            </button>
            <Button
              variant="primary"
              size="sm"
              isLoading={isLoading}
              onClick={handleUploadSubmit}
              className="shrink-0"
            >
              Upload
            </Button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border-2 border-dashed border-slate-300 hover:border-indigo-400 hover:bg-indigo-50/30 rounded-lg text-sm font-medium text-slate-700 hover:text-indigo-600 transition-all bg-white"
        >
          <UploadCloud className="w-4 h-4 text-indigo-500" />
          <span>Upload Audio / Video</span>
        </button>
      )}

      {error && <p className="mt-1.5 text-xs text-rose-600 font-medium">{error}</p>}
    </div>
  );
};
