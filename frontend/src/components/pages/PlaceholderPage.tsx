import { Construction } from 'lucide-react';

interface PlaceholderPageProps {
  title?: string;
  description: string;
}

export function PlaceholderPage({ description }: PlaceholderPageProps) {
  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full mb-4">
          <Construction className="w-8 h-8 text-slate-400" />
        </div>
        <p className="text-slate-600 dark:text-slate-400 max-w-md mb-4">
          {description}
        </p>
        <p className="text-sm text-slate-500">
          Coming in future updates
        </p>
      </div>
    </div>
  );
}
