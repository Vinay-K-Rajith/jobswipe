import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { IconMicrophone, IconPlayerStopFilled, IconSend, IconSparkles, IconVolume, IconVolumeOff } from '@tabler/icons-react';
import { completeSession, startInterview, submitAnswer, transcribeAudio } from '../../services/interviewApi';
import { useSpeech } from '../../hooks/useSpeech';
import { useAudioRecorder } from '../../hooks/useAudioRecorder';

interface Message {
  speaker: 'interviewer' | 'candidate';
  content: string;
}

const INTERVIEWER = { name: 'Jordan Lee', title: 'Interviewer', initials: 'JL' };

export default function InterviewRoom() {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [qNum, setQNum] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(true);
  const [done, setDone] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState('');
  const [voiceMode, setVoiceMode] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastSpokenRef = useRef(-1);

  const speech = useSpeech();       // TTS (interviewer voice)
  const recorder = useAudioRecorder(); // mic capture -> Groq Whisper

  useEffect(() => {
    startInterview(sessionId)
      .then((r) => {
        if (r.data.first_question) setMessages([{ speaker: 'interviewer', content: r.data.first_question }]);
        setQNum(r.data.question_number);
        setTotal(r.data.total_questions);
      })
      .catch((err) => setError(err?.response?.data?.detail || 'Could not start the interview.'))
      .finally(() => setStarting(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, transcribing, completing, done]);

  // Speak each new interviewer message when voice mode is on.
  useEffect(() => {
    if (!voiceMode || messages.length === 0) return;
    const lastIndex = messages.length - 1;
    const last = messages[lastIndex];
    if (last.speaker === 'interviewer' && lastIndex > lastSpokenRef.current) {
      lastSpokenRef.current = lastIndex;
      speech.speak(last.content);
    }
  }, [messages, voiceMode, speech]);

  const toggleVoice = () => {
    setVoiceMode((on) => {
      const next = !on;
      if (!next) {
        speech.cancelSpeak();
      } else {
        const last = messages[messages.length - 1];
        if (last?.speaker === 'interviewer') {
          lastSpokenRef.current = messages.length - 1;
          speech.speak(last.content);
        }
      }
      return next;
    });
  };

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading || done) return;
    setError('');
    setMessages((m) => [...m, { speaker: 'candidate', content: trimmed }]);
    setInput('');
    setLoading(true);
    try {
      const r = await submitAnswer(sessionId, trimmed);
      if (r.data.interviewer_turn) setMessages((m) => [...m, { speaker: 'interviewer', content: r.data.interviewer_turn as string }]);
      if (r.data.question_number) setQNum(r.data.question_number);
      if (r.data.total_questions) setTotal(r.data.total_questions);
      if (r.data.done) setDone(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not submit your answer. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecordToggle = async () => {
    if (recorder.recording) {
      recorder.stop(async (blob) => {
        setTranscribing(true);
        setError('');
        try {
          const res = await transcribeAudio(blob);
          const text = res.data.text?.trim();
          if (text) await submit(text);
          else setError('Did not catch that — please try again.');
        } catch (err: any) {
          setError(err?.response?.data?.detail || 'Transcription failed. Please try again.');
        } finally {
          setTranscribing(false);
        }
      });
    } else {
      speech.cancelSpeak(); // barge-in
      const ok = await recorder.start();
      if (!ok) setError('Microphone permission is required for voice mode.');
    }
  };

  const handleFinish = async () => {
    setCompleting(true);
    setError('');
    speech.cancelSpeak();
    try {
      await completeSession(sessionId);
      navigate(`/student/interview/${sessionId}/feedback`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not generate feedback. Try again.');
      setCompleting(false);
    }
  };

  const progress = total > 0 ? Math.min(100, Math.round((Math.min(qNum, total) / total) * 100)) : 0;

  const voiceStatus = transcribing
    ? 'Transcribing your answer…'
    : recorder.recording
      ? 'Listening… tap to finish'
      : loading
        ? 'Interviewer is responding…'
        : 'Tap the mic and speak your answer';

  return (
    <main className="portal-page">
      <div className="iv-wrap">
        <div className="iv-topbar">
          <div className="iv-avatar">{INTERVIEWER.initials}</div>
          <div className="iv-topbar__id">
            <b>{INTERVIEWER.name}</b>
            <span>{INTERVIEWER.title}{starting ? ' · connecting…' : loading ? ' · thinking…' : done ? ' · wrapping up' : recorder.recording ? ' · listening to you' : ' · ready'}</span>
          </div>
          <div className="iv-topbar__right">
            {(speech.ttsSupported || recorder.supported) && (
              <button
                type="button"
                className={`iv-btn iv-btn--ghost iv-btn--sm ${voiceMode ? 'iv-voice-on' : ''}`}
                onClick={toggleVoice}
                title={voiceMode ? 'Switch to text' : 'Switch to voice'}
              >
                {voiceMode ? <IconVolume size={15} /> : <IconVolumeOff size={15} />} Voice
              </button>
            )}
            <div className="iv-topbar__progress">
              <span>{total > 0 ? `Question ${Math.min(qNum, total)} of ${total}` : 'Mock interview'}</span>
              <div className="iv-progress"><div className="iv-progress__fill" style={{ width: `${done ? 100 : progress}%` }} /></div>
            </div>
          </div>
        </div>

        {error && <div className="bias-inline-error">{error}</div>}
        {voiceMode && !recorder.supported && (
          <div className="portal-note">Voice recording isn't supported in this browser — use Chrome or Edge, or switch back to text.</div>
        )}

        <div className="iv-thread">
          {messages.map((m, i) => (
            <div key={i} className={`iv-row ${m.speaker === 'interviewer' ? 'iv-row--ai' : 'iv-row--me'}`}>
              <div className={`iv-avatar ${m.speaker === 'interviewer' ? '' : 'iv-avatar--me'}`}>
                {m.speaker === 'interviewer' ? INTERVIEWER.initials : 'You'}
              </div>
              <div>
                <div className="iv-who" style={{ textAlign: m.speaker === 'interviewer' ? 'left' : 'right' }}>
                  {m.speaker === 'interviewer' ? INTERVIEWER.name : 'You'}
                </div>
                <div className="iv-bubble">{m.content}</div>
              </div>
            </div>
          ))}
          {(loading || transcribing || (starting && messages.length === 0)) && (
            <div className="iv-row iv-row--ai">
              <div className="iv-avatar">{INTERVIEWER.initials}</div>
              <div className="iv-typing"><span /><span /><span /></div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {done ? (
          <div className="iv-card iv-card--accent iv-finish">
            <span className="iv-hero__eyebrow"><IconSparkles size={14} /> Interview complete</span>
            <p style={{ margin: 0, color: 'var(--text-secondary)' }}>That's the end of the interview. Generate your feedback when you're ready.</p>
            <button className="iv-btn" type="button" onClick={handleFinish} disabled={completing}>
              {completing ? 'Analyzing your interview…' : 'Get my feedback'}
            </button>
          </div>
        ) : voiceMode && recorder.supported ? (
          <div className="iv-dock iv-voicebar">
            <button
              type="button"
              className={`iv-mic iv-mic--lg ${recorder.recording ? 'iv-mic--on' : ''}`}
              onClick={handleRecordToggle}
              disabled={loading || starting || transcribing}
              title={recorder.recording ? 'Stop & send' : 'Record answer'}
            >
              {recorder.recording ? <IconPlayerStopFilled size={26} /> : <IconMicrophone size={26} />}
            </button>
            <span className="iv-voice-status">{voiceStatus}</span>
          </div>
        ) : (
          <div className="iv-dock">
            <textarea
              className="iv-textarea"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit(input); }}
              placeholder="Type your answer… (Ctrl/Cmd + Enter to send)"
              rows={4}
              disabled={loading || starting}
            />
            <div className="iv-dock__actions">
              <span className="iv-hint">No scores — just honest feedback at the end.</span>
              <button className="iv-btn" type="button" onClick={() => submit(input)} disabled={loading || starting || !input.trim()}>
                <IconSend size={16} /> {loading ? 'Sending…' : 'Send'}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
