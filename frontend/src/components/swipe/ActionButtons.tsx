import { IconCheck, IconX } from '@tabler/icons-react';

interface ActionButtonsProps {
  onPass: () => void;
  onLike: () => void;
  disabled?: boolean;
}

export default function ActionButtons({ onPass, onLike, disabled }: ActionButtonsProps) {
  return (
    <div className="swipe-actions">
      <button className="swipe-action pass" onClick={onPass} disabled={disabled} type="button" aria-label="Pass">
        <IconX size={22} />
        <span>Pass</span>
      </button>
      <button className="swipe-action like" onClick={onLike} disabled={disabled} type="button" aria-label="Like">
        <IconCheck size={22} />
        <span>Like</span>
      </button>
    </div>
  );
}
