"use client";

import React, { useCallback, useState } from "react";
import { Upload, FileText, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface FileUploadZoneProps {
  onFileSelect: (file: File) => void;
  acceptedTypes?: string;
}

export function FileUploadZone({ onFileSelect, acceptedTypes = ".pdf,.doc,.docx" }: FileUploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect]);

  const clearFile = useCallback(() => {
    setSelectedFile(null);
  }, []);

  return (
    <div className="w-full">
      <AnimatePresence mode="wait">
        {selectedFile ? (
          <motion.div
            key="file-selected"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-4"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500">
              <FileText className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground">
                {(selectedFile.size / 1024).toFixed(1)} KB
              </p>
            </div>
            <button
              onClick={clearFile}
              className="rounded-lg p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </motion.div>
        ) : (
          <motion.label
            key="drop-zone"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed
              p-8 cursor-pointer transition-all duration-200
              ${isDragOver
                ? "border-emerald-500 bg-emerald-500/5 scale-[1.02]"
                : "border-border bg-card/50 hover:border-primary/50 hover:bg-card"
              }
            `}
          >
            <input
              type="file"
              accept={acceptedTypes}
              onChange={handleFileInput}
              className="sr-only"
            />
            <div className={`rounded-full p-3 transition-colors ${isDragOver ? "bg-emerald-500/10 text-emerald-500" : "bg-muted text-muted-foreground"}`}>
              <Upload className="h-6 w-6" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium">
                Drop your document here, or <span className="text-primary underline underline-offset-2">browse</span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Supports PDF, DOCX up to 10MB
              </p>
            </div>
          </motion.label>
        )}
      </AnimatePresence>
    </div>
  );
}
