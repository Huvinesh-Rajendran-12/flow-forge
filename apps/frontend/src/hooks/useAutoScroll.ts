import { useEffect, useRef, useState } from 'react';

export function useAutoScroll<T extends HTMLElement>(dependencies: unknown[]) {
  const ref = useRef<T>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [...dependencies, autoScroll]);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = element;
      const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 50;
      setAutoScroll(isAtBottom);
    };

    element.addEventListener('scroll', handleScroll);
    return () => element.removeEventListener('scroll', handleScroll);
  }, []);

  return ref;
}
