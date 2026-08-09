import { useEffect, useRef, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { Card, CardContent } from './Card';
import { Button } from './Button';

interface ConfirmModalProps {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  cancelVariant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  cardClassName?: string;
  // Tailwind z-index utility applied to the fixed overlay. Defaults to
  // ``z-50``. Use a higher value (e.g. ``z-[110]``) when this confirm
  // dialog is rendered from inside another modal that uses ``z-[100]`` —
  // without it the confirm dialog sits behind its parent (#1336 follow-up).
  overlayZIndex?: string;
  variant?: 'danger' | 'warning' | 'default';
  isLoading?: boolean;
  loadingText?: string;
  // Disable the confirm button without a loading spinner. Used when an
  // external precondition forbids the action (e.g. #1734 — a related queue
  // item is mid-print, so the archive delete must be blocked at the UI
  // layer too even though the backend will 409 anyway).
  confirmDisabled?: boolean;
  // Optional extra content rendered between the message and the buttons —
  // used for opt-in checkboxes (e.g. the "Also remove from statistics"
  // toggle in the archive delete confirmation, #1343).
  children?: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  title,
  message,
  confirmText,
  cancelText,
  cancelVariant,
  cardClassName,
  overlayZIndex,
  variant = 'default',
  isLoading = false,
  loadingText,
  confirmDisabled = false,
  children,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const { t } = useTranslation();
  const resolvedConfirmText = confirmText ?? t('common.confirm');
  const resolvedCancelText = cancelText ?? t('common.cancel');
  const resolvedLoadingText = loadingText ?? t('common.loading');
  // Native dialogs keep focus inside the confirmation and supply a real
  // backdrop.  The close request is still owned by the caller so mutations
  // cannot be dismissed while pending.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) return;
    if (typeof dialog.showModal === 'function') dialog.showModal();
    // JSDOM does not implement showModal; retaining the open attribute keeps
    // the semantic dialog testable without changing browser behaviour.
    else dialog.setAttribute('open', '');
    return () => {
      if (dialog.open) dialog.close?.();
    };
  }, []);

  const variantStyles = {
    danger: {
      icon: 'text-bambu-green',
      button: '',
    },
    warning: {
      icon: 'text-bambu-green',
      button: '',
    },
    default: {
      icon: 'text-bambu-green',
      button: '',
    },
  };

  const styles = variantStyles[variant];

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="confirmation-title"
      className={`nocturne-confirm-dialog w-full max-w-md ${overlayZIndex ?? ''}`}
      onCancel={(event) => {
        event.preventDefault();
        if (!isLoading) onCancel();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget && !isLoading) onCancel();
      }}
    >
      <Card
        className={`w-full max-w-md ${cardClassName ?? ''}`}
      >
        <CardContent className="p-6">
          <div className="flex items-start gap-4">
            <div className={`p-2 rounded-full bg-bambu-dark ${styles.icon}`}>
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="flex-1">
              <h3 id="confirmation-title" className="text-lg font-medium text-white mb-2">{title}</h3>
              <p className="text-bambu-gray text-sm whitespace-pre-line">{message}</p>
              {children && <div className="mt-4">{children}</div>}
            </div>
          </div>
          <div className="flex gap-3 mt-6">
            <Button
              variant={cancelVariant ?? 'secondary'}
              onClick={onCancel}
              className="flex-1"
              disabled={isLoading}
            >
              {resolvedCancelText}
            </Button>
            <Button
              onClick={onConfirm}
              className={`flex-1 ${styles.button}`}
              disabled={isLoading || confirmDisabled}
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {resolvedLoadingText}
                </>
              ) : (
                resolvedConfirmText
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </dialog>
  );
}
