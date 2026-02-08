import { HTMLAttributes, forwardRef } from 'react';
import { cn } from '../../utils/cn';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'error' | 'warning' | 'running';
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center px-2 py-0.5 rounded text-xs font-mono border border-dotted',
          {
            'border-terminal-border text-terminal-text-dim bg-terminal-card': variant === 'default',
            'border-terminal-green-dim text-terminal-green-muted bg-terminal-green-dim/20': variant === 'success',
            'border-red-900 text-terminal-red bg-red-950/50': variant === 'error',
            'border-yellow-900 text-terminal-yellow bg-yellow-950/50': variant === 'warning',
            'border-cyan-900 text-terminal-cyan bg-cyan-950/50 animate-pulse-green': variant === 'running',
          },
          className
        )}
        {...props}
      />
    );
  }
);

Badge.displayName = 'Badge';
