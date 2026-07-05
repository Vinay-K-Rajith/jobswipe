import { useCallback, useEffect, useRef, useState } from 'react';

// Minimal typings for the Web Speech API (not in the standard TS lib).
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: any) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: any) => void) | null;
};

function getRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === 'undefined') return null;
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null;
}

/**
 * Browser-native speech: text-to-speech for the interviewer and speech-to-text
 * for the candidate. Works in Chromium browsers; degrades gracefully elsewhere.
 */
export function useSpeech() {
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const finalRef = useRef('');
  const onFinalRef = useRef<((text: string) => void) | null>(null);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState('');

  const sttSupported = !!getRecognitionCtor();
  const ttsSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

  const cancelSpeak = useCallback(() => {
    if (ttsSupported) window.speechSynthesis.cancel();
  }, [ttsSupported]);

  const speak = useCallback(
    (text: string) => {
      if (!ttsSupported || !text) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'en-US';
      utterance.rate = 1;
      utterance.pitch = 1;
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find((v) => /en-US/i.test(v.lang) && /natural|google|en-US/i.test(v.name))
        || voices.find((v) => /en/i.test(v.lang));
      if (preferred) utterance.voice = preferred;
      window.speechSynthesis.speak(utterance);
    },
    [ttsSupported],
  );

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const startListening = useCallback(
    (onFinal: (text: string) => void) => {
      const Ctor = getRecognitionCtor();
      if (!Ctor) return;
      // barge-in: stop any TTS so the mic doesn't capture it
      if (ttsSupported) window.speechSynthesis.cancel();

      const rec = new Ctor();
      rec.lang = 'en-US';
      rec.continuous = true;
      rec.interimResults = true;
      finalRef.current = '';
      onFinalRef.current = onFinal;

      rec.onresult = (e: any) => {
        let interimText = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const result = e.results[i];
          if (result.isFinal) finalRef.current += result[0].transcript;
          else interimText += result[0].transcript;
        }
        setInterim((finalRef.current + interimText).trim());
      };
      rec.onerror = () => setListening(false);
      rec.onend = () => {
        setListening(false);
        const text = finalRef.current.trim();
        setInterim('');
        if (text) onFinalRef.current?.(text);
      };

      recognitionRef.current = rec;
      setInterim('');
      setListening(true);
      try {
        rec.start();
      } catch {
        setListening(false);
      }
    },
    [ttsSupported],
  );

  useEffect(() => {
    return () => {
      try {
        recognitionRef.current?.stop();
      } catch {
        // ignore
      }
      if (ttsSupported) window.speechSynthesis.cancel();
    };
  }, [ttsSupported]);

  return { sttSupported, ttsSupported, listening, interim, speak, cancelSpeak, startListening, stopListening };
}
