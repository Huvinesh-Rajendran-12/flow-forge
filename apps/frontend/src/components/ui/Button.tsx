import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../utils/cn';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'px-4 py-2 rounded font-mono text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed',
          {
            'bg-terminal-green text-terminal-bg hover:shadow-[0_0_10px_rgba(0,255,65,0.3)] active:bg-terminal-green-muted':
              variant === 'primary',
            'bg-transparent text-terminal-green border border-dashed border-terminal-green hover:bg-terminal-green/10':
              variant === 'secondary',
            'bg-transparent text-terminal-green-muted hover:text-terminal-green hover:bg-terminal-card':
              variant === 'ghost',
          },
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';
