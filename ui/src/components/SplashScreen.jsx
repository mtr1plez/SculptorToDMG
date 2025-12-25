import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

export function SplashScreen({ onReady }) {
  const [status, setStatus] = useState('Initializing...');
  const [progress, setProgress] = useState(0);
  const [dots, setDots] = useState('');

  useEffect(() => {
    // Анимация точек
    const dotsInterval = setInterval(() => {
      setDots(prev => prev.length >= 3 ? '' : prev + '.');
    }, 500);

    return () => clearInterval(dotsInterval);
  }, []);

  useEffect(() => {
    let mounted = true;
    let retries = 0;
    const maxRetries = 60; // 60 секунд максимум

    const checkServer = async () => {
      try {
        setStatus('Starting AI Engine');
        setProgress(20);

        const response = await fetch('http://localhost:8000/status', {
          signal: AbortSignal.timeout(2000)
        });

        if (response.ok && mounted) {
          setStatus('Loading Models');
          setProgress(60);
          
          // Даем время на финальную инициализацию
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          setStatus('Ready!');
          setProgress(100);
          
          setTimeout(() => {
            if (mounted) onReady();
          }, 500);
          
          return;
        }
      } catch (error) {
        // Сервер еще не готов
      }

      retries++;
      
      if (retries > maxRetries) {
        setStatus('Connection timeout. Please restart the app.');
        return;
      }

      // Обновляем прогресс
      setProgress(Math.min(15 + (retries * 0.5), 50));

      // Повторяем проверку
      setTimeout(() => {
        if (mounted) checkServer();
      }, 1000);
    };

    // Небольшая задержка перед первой проверкой
    setTimeout(() => {
      if (mounted) checkServer();
    }, 500);

    return () => {
      mounted = false;
    };
  }, [onReady]);

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-zinc-950 via-black to-zinc-900 flex items-center justify-center z-50">
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center">
        {/* Logo */}
        <div className="mb-8 relative">
          <div className="w-32 h-32 relative">
            <img 
              src="/app-icon.png" 
              alt="SculptorPro" 
              className="w-full h-full object-contain drop-shadow-2xl"
            />
            
            {/* Spinning ring */}
            <div className="absolute inset-0 border-4 border-accent/20 border-t-accent rounded-full animate-spin"></div>
          </div>
        </div>

        {/* App name */}
        <h1 className="text-4xl font-bold text-white mb-2 tracking-tight">
          SCULPTOR PRO
        </h1>
        
        {/* Status text */}
        <div className="flex items-center gap-2 text-zinc-400 mb-8 h-6">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm font-medium min-w-[200px]">
            {status}{dots}
          </span>
        </div>

        {/* Progress bar */}
        <div className="w-80 h-2 bg-zinc-800 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-accent to-purple-500 transition-all duration-500 ease-out rounded-full shadow-lg shadow-accent/50"
            style={{ width: `${progress}%` }}
          ></div>
        </div>

        {/* Version */}
        <p className="text-xs text-zinc-600 mt-8">
          Version 1.0.0
        </p>
      </div>
    </div>
  );
}