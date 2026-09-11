import React from 'react';

const LoadingSpinner = () => {
  return (
    <div className="flex items-center justify-center p-8 bg-black/40 border border-cyan-500/20 rounded-lg">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
        <span className="text-xs text-cyan-400 font-mono">Loading...</span>
      </div>
    </div>
  );
};

export default LoadingSpinner;