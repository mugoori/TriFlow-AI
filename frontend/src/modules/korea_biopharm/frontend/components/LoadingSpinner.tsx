interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  text?: string;
}

export default function LoadingSpinner({ size = 'md', text }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className="flex flex-col items-center justify-center py-8">
      <div
        className={`
          ${sizeClasses[size]}
          border-4 border-blue-200 border-t-primary-600
          rounded-full animate-spin
        `}
      />
      {text && <p className="mt-3 text-gray-600 text-sm">{text}</p>}
    </div>
  );
}
