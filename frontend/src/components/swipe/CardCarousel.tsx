import { useEffect, useMemo, useState } from 'react';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';
import ActionButtons from './ActionButtons';

interface CardCarouselProps<T> {
  items: T[];
  getKey: (item: T) => string;
  renderCard: (item: T, expanded: boolean, toggleExpanded: () => void) => JSX.Element;
  onPass: (item: T) => Promise<void> | void;
  onLike: (item: T) => Promise<void> | void;
  emptyTitle: string;
  emptyText: string;
}

export default function CardCarousel<T>({
  items,
  getKey,
  renderCard,
  onPass,
  onLike,
  emptyTitle,
  emptyText,
}: CardCarouselProps<T>) {
  const [index, setIndex] = useState(0);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const current = items[index];
  const currentKey = current ? getKey(current) : '';

  useEffect(() => {
    if (index >= items.length) setIndex(Math.max(0, items.length - 1));
  }, [index, items.length]);

  const trackStyle = useMemo(() => ({
    transform: `translateX(${-index * 340}px)`,
  }), [index]);

  function move(delta: number) {
    setExpandedKey(null);
    setIndex((value) => Math.min(Math.max(value + delta, 0), Math.max(items.length - 1, 0)));
  }

  async function decide(kind: 'pass' | 'like') {
    if (!current || busy) return;
    setBusy(true);
    try {
      if (kind === 'pass') await onPass(current);
      else await onLike(current);
      setExpandedKey(null);
      setIndex((value) => Math.min(value, Math.max(items.length - 2, 0)));
    } finally {
      setBusy(false);
    }
  }

  function toggleExpanded() {
    if (!currentKey) return;
    setExpandedKey((value) => (value === currentKey ? null : currentKey));
  }

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        void decide('pass');
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        void decide('like');
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggleExpanded();
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  });

  if (!items.length) {
    return (
      <div className="portal-empty">
        <h2>{emptyTitle}</h2>
        <p>{emptyText}</p>
      </div>
    );
  }

  return (
    <section className="carousel-shell">
      <div className="carousel-viewport">
        <div className="carousel-track" style={trackStyle}>
          {items.map((item, itemIndex) => {
            const key = getKey(item);
            const offset = itemIndex - index;
            return (
              <div
                className={`carousel-slot ${offset === 0 ? 'active' : ''}`}
                key={key}
                aria-hidden={Math.abs(offset) > 1}
              >
                {renderCard(item, expandedKey === key, () => setExpandedKey(expandedKey === key ? null : key))}
              </div>
            );
          })}
        </div>
      </div>
      <ActionButtons onPass={() => void decide('pass')} onLike={() => void decide('like')} disabled={busy} />
      <div className="keyboard-hint">Left pass / Right like / Space expand</div>
      <div className="carousel-nav">
        <button type="button" onClick={() => move(-1)} disabled={index === 0} aria-label="Previous card">
          <IconChevronLeft size={20} />
        </button>
        <button type="button" onClick={() => move(1)} disabled={index === items.length - 1} aria-label="Next card">
          <IconChevronRight size={20} />
        </button>
      </div>
    </section>
  );
}
