import React, { useState } from 'react';
import { Button, type ButtonSize, type ButtonVariant } from './Button';

export interface CopyButtonProps {
  value: string | (() => string);
  label?: string;
  copiedLabel?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
  allowShare?: boolean;
  shareTitle?: string;
}

export const CopyButton: React.FC<CopyButtonProps> = ({
  value,
  label = 'Скопировать',
  copiedLabel = 'Скопировано!',
  variant = 'secondary',
  size = 'sm',
  title = 'Скопировать в буфер обмена',
  className = '',
  style,
  allowShare = false,
  shareTitle,
}) => {
  const [copied, setCopied] = useState(false);

  const canShare = allowShare && typeof navigator !== 'undefined' && Boolean(navigator.share);

  const handleCopy = async () => {
    const text = typeof value === 'function' ? value() : value;
    if (!text) return;

    if (canShare) {
      try {
        await navigator.share({
          title: shareTitle || document.title,
          url: text.startsWith('http') ? text : undefined,
          text: !text.startsWith('http') ? text : undefined,
        });
        return;
      } catch (err) {
        // User cancelled or share failed, fallback to copy below
        if ((err as Error).name === 'AbortError') return;
      }
    }

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        // Fallback for older browsers or restricted environments
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        textArea.style.top = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <Button
      type="button"
      variant={copied ? 'brand' : variant}
      size={size}
      onClick={handleCopy}
      title={copied ? copiedLabel : title}
      className={`sc-copy-btn ${copied ? 'is-copied' : ''} ${className}`}
      style={style}
      aria-label={copied ? copiedLabel : title}
    >
      <span aria-hidden="true" style={{ fontSize: '0.9em' }}>
        {copied ? '✓' : canShare ? '↗' : '📋'}
      </span>
      <span>{copied ? copiedLabel : label}</span>
      <span className="sr-only" aria-live="polite">
        {copied ? copiedLabel : ''}
      </span>
    </Button>
  );
};
