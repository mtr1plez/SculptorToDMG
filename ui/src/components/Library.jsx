import { useState, useEffect, useRef } from 'react';
import { Film, CheckCircle, AlertCircle, Loader2, Trash2 } from 'lucide-react'; // Добавил Trash2
import { IngestModal } from './IngestModal';
import { CircularProgress } from './CircularProgress';

export function Library() {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const [progressMap, setProgressMap] = useState({});
  const [contextMenu, setContextMenu] = useState(null);

  const fetchLibraryRef = useRef(null);

  // === 1. ФУНКЦИЯ ЗАГРУЗКИ БИБЛИОТЕКИ ===
  const fetchLibrary = () => {
    fetch('http://localhost:8000/library')
      .then(res => res.json())
      .then(data => {
        setMovies(data);
        
        // === НОВОЕ: Восстанавливаем статус обработки ===
        const restoredProgress = {};
        data.forEach(movie => {
          if (movie.ingest_status === 'processing' && movie.percent < 100) {
            restoredProgress[movie.alias] = {
              percent: movie.percent,
              status: movie.progress_text
            };
          }
        });
        
        if (Object.keys(restoredProgress).length > 0) {
          setProgressMap(restoredProgress);
        }
        
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError(true);
        setLoading(false);
      });
  };


  fetchLibraryRef.current = fetchLibrary;

  useEffect(() => {
    fetchLibrary();
  }, []);

  // === 2. ЗАКРЫТИЕ МЕНЮ ПО КЛИКУ ===
  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, []);

  // === 3. WEBSOCKET ===
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/logs');

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'progress') {
          setProgressMap(prev => ({
            ...prev,
            [data.alias]: { percent: data.percent, status: data.status }
          }));

          if (data.percent === 100) {
            setTimeout(() => {
              if (fetchLibraryRef.current) fetchLibraryRef.current();
              setProgressMap(prev => {
                const newState = { ...prev };
                delete newState[data.alias];
                return newState;
              });
            }, 1000);
          }
        }
      } catch (e) {}
    };

    return () => ws.close();
  }, []);

  // === 4. ОБРАБОТЧИКИ (DELETE / CONTEXT MENU) ===
  const handleContextMenu = (e, movie) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      x: e.pageX,
      y: e.pageY,
      movie: movie
    });
  };

  const handleDelete = async (alias) => {
    if (!confirm(`Are you sure you want to delete "${alias}" from Library? This cannot be undone.`)) return;

    try {
      await fetch(`http://localhost:8000/library/${alias}`, { method: 'DELETE' });
      fetchLibrary(); 
    } catch (e) {
      alert("Failed to delete movie");
    }
  };


  // === РЕНДЕР ===

  if (loading) return (
    <div className="flex h-full items-center justify-center text-muted gap-2">
      <Loader2 className="animate-spin" /> Loading Library...
    </div>
  );

  if (error) return (
    <div className="flex h-full items-center justify-center text-red-400 gap-2">
      <AlertCircle /> Connection failed. Is python server running?
    </div>
  );

  return (
    <div className="p-8 h-full overflow-y-auto relative min-h-screen">
      <IngestModal 
        isOpen={isIngestOpen} 
        onClose={() => setIsIngestOpen(false)} 
        onIngestSuccess={() => {
          setIsIngestOpen(false);
          fetchLibrary();
        }}
      />

      {/* === КОНТЕКСТНОЕ МЕНЮ === */}
      {contextMenu && (
        <div 
          className="fixed z-50 bg-zinc-800 border border-zinc-700 shadow-xl rounded-lg py-1 min-w-[160px] animate-in fade-in zoom-in-95 duration-100"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="px-3 py-2 text-xs text-zinc-500 border-b border-zinc-700 mb-1">
             {contextMenu.movie.alias}
          </div>
          <button 
            onClick={() => {
                handleDelete(contextMenu.movie.alias);
                setContextMenu(null);
            }}
            className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 flex items-center gap-2 transition-colors"
          >
            <Trash2 size={14} /> Delete Movie
          </button>
        </div>
      )}

      <header className="mb-8 flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-primary">Media Library</h2>
          <p className="text-muted text-sm mt-1">Manage your source footage</p>
        </div>
        <button 
          onClick={() => setIsIngestOpen(true)}
          className="bg-accent hover:bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg shadow-blue-900/20"
        >
          + Ingest Movie
        </button>
      </header>

      {movies.length === 0 ? (
        <div className="text-center py-20 border border-dashed border-border rounded-xl">
          <Film className="w-12 h-12 text-muted mx-auto mb-3 opacity-20" />
          <p className="text-muted">Library is empty</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 pb-20">
          {movies.map((movie) => {
            const activeProgress = progressMap[movie.alias];
            const isProcessing = !movie.ready || activeProgress;
            const percent = activeProgress?.percent || 0;
            const statusText = activeProgress?.status || "Queued...";

            return (
              <div 
                key={movie.alias} 
                onContextMenu={(e) => handleContextMenu(e, movie)} // <--- ДОБАВИЛИ ОБРАБОТЧИК
                className="group bg-surface border border-border rounded-xl overflow-hidden hover:border-accent/50 transition-all cursor-pointer relative shadow-lg"
              >
                
                <div className="h-64 bg-zinc-900 flex items-center justify-center relative overflow-hidden">
                  {movie.thumbnail ? (
                    <img 
                      src={movie.thumbnail} 
                      alt={movie.alias} 
                      className={`w-full h-full object-cover transition-all duration-500 
                        ${isProcessing ? 'opacity-30 blur-sm scale-105' : 'opacity-90 group-hover:opacity-100 group-hover:scale-105'}
                      `}
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                  ) : (
                    <Film className="text-zinc-700 w-16 h-16" />
                  )}

                  {isProcessing && (
                    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/40 backdrop-blur-[2px]">
                       <CircularProgress percent={percent} size={60} />
                       <span className="text-xs font-medium text-yellow-400 mt-3 px-2 py-1 bg-black/60 rounded-full border border-yellow-500/20">
                         {statusText}
                       </span>
                    </div>
                  )}

                  {!isProcessing && (
                    <div className="absolute top-3 right-3 z-10">
                      <span className="bg-black/60 backdrop-blur-md text-green-400 text-xs px-2 py-1 rounded-md flex items-center gap-1 border border-green-500/30 font-medium shadow-sm">
                        <CheckCircle size={12} /> Ready
                      </span>
                    </div>
                  )}
                  
                  <div className="absolute bottom-0 left-0 w-full h-2/3 bg-gradient-to-t from-black via-black/50 to-transparent opacity-80 pointer-events-none"></div>
                </div>

                <div className="absolute bottom-0 left-0 w-full p-4 z-20">
                  <h3 className="font-bold text-xl text-white drop-shadow-md truncate">{movie.alias}</h3>
                  <p className="text-xs text-gray-300 mt-1 truncate opacity-80">{movie.path}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}