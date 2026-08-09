import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  children: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonProps) {
  const baseStyles =
    'nocturne-button inline-flex items-center justify-center font-medium rounded-md transition-colors focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'border border-bambu-green bg-transparent text-bambu-green hover:bg-bambu-green/10',
    secondary:
      'border border-bambu-dark-tertiary bg-transparent text-bambu-gray-light hover:border-bambu-green hover:text-bambu-green hover:bg-bambu-green/10',
    danger: 'border border-bambu-green bg-transparent text-bambu-green hover:bg-bambu-green/10',
    ghost:
      'border border-transparent bg-transparent text-bambu-gray-light hover:border-bambu-dark-tertiary hover:text-bambu-green',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm gap-1.5 min-h-[44px] md:min-h-0',
    md: 'px-4 py-2 text-sm gap-2 min-h-[44px] md:min-h-0',
    lg: 'px-6 py-3 text-base gap-2 min-h-[48px] md:min-h-0',
  };

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
