import { HTMLAttributes, forwardRef } from 'react';
import { cn } from '../../utils/cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'bg-terminal-card border border-dashed border-terminal-border rounded p-3',
          className
        )}
        {...props}
      />
    );
  }
);

Card.displayName = 'Card';
