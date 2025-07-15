interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'pending' | 'error';
  label?: string;
}

export default function StatusIndicator({ status, label }: StatusIndicatorProps) {
  const statusColors = {
    online: 'bg-green-500',
    offline: 'bg-gray-400',
    pending: 'bg-yellow-500',
    error: 'bg-red-500'
  };

  return (
    <div className="flex items-center space-x-2">
      <div className="relative">
        <div className={`h-3 w-3 rounded-full ${statusColors[status]}`}>
          {status === 'online' && (
            <div className={`absolute inset-0 rounded-full ${statusColors[status]} animate-ping opacity-75`}></div>
          )}
        </div>
      </div>
      {label && <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>}
    </div>
  );
}