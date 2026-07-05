import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Records mic audio via MediaRecorder and hands back a Blob on stop.
 * Used by voice mode to capture spoken answers for server-side (Groq Whisper) STT.
 */
export function useAudioRecorder() {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const onStopRef = useRef<((blob: Blob) => void) | null>(null);
  const [recording, setRecording] = useState(false);

  const supported =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined';

  const start = useCallback(async (): Promise<boolean> => {
    if (!supported) return false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        setRecording(false);
        onStopRef.current?.(blob);
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
      return true;
    } catch {
      setRecording(false);
      return false;
    }
  }, [supported]);

  const stop = useCallback((onStop: (blob: Blob) => void) => {
    onStopRef.current = onStop;
    try {
      recorderRef.current?.stop();
    } catch {
      setRecording(false);
    }
  }, []);

  useEffect(() => {
    return () => {
      try {
        recorderRef.current?.stop();
      } catch {
        // ignore
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { supported, recording, start, stop };
}
