// Copyright (c) 2025 SNF-AI
// SPDX-License-Identifier: MIT

import { useState, useCallback } from 'react';

// API base URL
const API_BASE_URL = 'http://127.0.0.1:5002';

// Upload response interface
export interface UploadResponse {
  success: boolean;
  file_id: string;
  file_path: string;
  file_type: string;
  original_name: string;
  extension: string;
  size_bytes: number;
  created_at: number;
  mime_type: string | null;
  sha256: string;
}

// Hook return type
interface UseUploadReturn {
  uploadFile: (file: File, type?: string) => Promise<UploadResponse>;
  uploadFiles: (files: File[]) => Promise<UploadResponse[]>;
  uploading: boolean;
  error: string | null;
}

/**
 * Custom hook for handling file uploads to the Flux API
 */
export function useUpload(): UseUploadReturn {
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Upload a single file to the API
   */
  const uploadFile = useCallback(async (file: File, type?: string): Promise<UploadResponse> => {
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('image', file);
      
      // Add file type if provided
      if (type) {
        formData.append('type', type);
      } else {
        // Auto-detect type from file extension
        const extension = file.name.split('.').pop()?.toLowerCase();
        if (extension) {
          if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(extension)) {
            formData.append('type', 'image');
          } else if (['pdf', 'doc', 'docx', 'txt', 'md'].includes(extension)) {
            formData.append('type', 'document');
          } else if (['mp3', 'wav', 'ogg', 'flac'].includes(extension)) {
            formData.append('type', 'audio');
          } else if (['mp4', 'webm', 'avi', 'mov'].includes(extension)) {
            formData.append('type', 'video');
          }
        }
      }

      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Upload failed: ${response.statusText}`);
      }

      const data: UploadResponse = await response.json();
      return data;
    } catch (err) {
      console.error('Error uploading file:', err);
      setError(`Upload failed: ${err instanceof Error ? err.message : String(err)}`);
      throw err;
    } finally {
      setUploading(false);
    }
  }, []);

  /**
   * Upload multiple files to the API
   */
  const uploadFiles = useCallback(async (files: File[]): Promise<UploadResponse[]> => {
    setUploading(true);
    setError(null);

    try {
      // Upload files in parallel
      const uploadPromises = files.map(file => {
        // Auto-detect type from file extension
        const extension = file.name.split('.').pop()?.toLowerCase();
        let type: string | undefined;
        
        if (extension) {
          if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(extension)) {
            type = 'image';
          } else if (['pdf', 'doc', 'docx', 'txt', 'md'].includes(extension)) {
            type = 'document';
          } else if (['mp3', 'wav', 'ogg', 'flac'].includes(extension)) {
            type = 'audio';
          } else if (['mp4', 'webm', 'avi', 'mov'].includes(extension)) {
            type = 'video';
          }
        }
        
        return uploadFile(file, type);
      });

      return await Promise.all(uploadPromises);
    } catch (err) {
      console.error('Error uploading files:', err);
      setError(`Upload failed: ${err instanceof Error ? err.message : String(err)}`);
      throw err;
    } finally {
      setUploading(false);
    }
  }, [uploadFile]);

  return {
    uploadFile,
    uploadFiles,
    uploading,
    error,
  };
}

export default useUpload;
