import { InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../utils/cn';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          'w-full px-3 py-2 bg-terminal-bg border border-dashed border-terminal-border rounded font-mono text-sm text-terminal-green caret-terminal-green placeholder:text-terminal-text-dim focus:outline-none focus:border-terminal-green focus:shadow-[0_0_5px_rgba(0,255,65,0.2)]',
          className
        )}
        {...props}
      />
    );
  }
);

Input.displayName = 'Input';
