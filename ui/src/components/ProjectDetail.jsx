import { useState, useEffect } from 'react';
import { ArrowLeft, Music, Film, Trash2, Wand2, Loader2, FolderOpen, CheckCircle, Folder } from 'lucide-react';
import { SourceSelector } from './SourceSelector';
import { CircularProgress } from './CircularProgress';

const { ipcRenderer } = window.require('electron');

export function ProjectDetail({ project, onBack }) {
  const [sources, setSources] = useState([]); 
  const [audioPath, setAudioPath] = useState('');
  const [audioReadyOnServer, setAudioReadyOnServer] = useState(false);
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);
  const [projectStatus, setProjectStatus] = useState('idle');
  const [buildPercent, setBuildPercent] = useState(0);
  const [buildText, setBuildText] = useState("Initializing...");

  // === 1. ЗАГРУЖАЕМ ДАННЫЕ ===
  useEffect(() => {
  // Функция для загрузки актуального состояния
  const loadProjectState = () => {
    fetch(`http://localhost:8000/projects/${project.name}`)
      .then(res => res.json())
      .then(data => {
        if (data && !data.error) {
          // Sources
          if (data.sources) setSources(data.sources);
          
          // Audio
          if (data.audio_ready) {
            setAudioReadyOnServer(true);
            setAudioPath("Ready on Server");
          }
          
          // Status & Progress (КЛЮЧЕВОЕ ИЗМЕНЕНИЕ)
          const status = data.status || 'idle';
          setProjectStatus(status);
          
          if (status === 'building') {
            // Восстанавливаем прогресс из файла
            setBuildPercent(data.percent || 0);
            setBuildText(data.progress_text || "Resuming...");
          } else if (status === 'ready') {
            setBuildPercent(100);
            setBuildText("Build complete");
          } else {
            // idle
            setBuildPercent(0);
            setBuildText("Initializing...");
          }
        }
      })
      .catch(err => console.error("Failed to load project state:", err));
  };

  // Загружаем сразу
  loadProjectState();

  // ОПЦИОНАЛЬНО: Обновляем каждые 2 секунды, если статус building
  // (На случай, если WebSocket не подключился)
  const interval = setInterval(() => {
    if (projectStatus === 'building') {
      loadProjectState();
    }
  }, 2000);

  return () => clearInterval(interval);
}, [project.name, projectStatus]);

  // === 2. СЛУШАЕМ WEBSOCKET ===
  useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/ws/logs');
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      if (data.type === 'progress' && data.alias === project.name) {
        // Обновляем UI
        setBuildPercent(data.percent);
        setBuildText(data.status);
        
        // Обновляем статус на основе процента
        if (data.percent >= 100) {
          setProjectStatus('ready');
        } else if (data.percent > 0) {
          setProjectStatus('building');
        }
      }
    } catch(e) {
      // Ignore non-JSON messages
    }
  };

  ws.onerror = (err) => console.error('WebSocket error:', err);
  ws.onclose = () => console.log('WebSocket closed');

  return () => ws.close();
}, [project.name]);


  const handleStartBuild = async () => {
    if (sources.length === 0 || (!audioPath && !audioReadyOnServer)) return;
    
    setProjectStatus('building'); // Сразу меняем UI
    setBuildPercent(0);
    setBuildText("Starting...");

    try {
      await fetch('http://localhost:8000/build', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_name: project.name,
          sources: sources,
          audio_path: audioReadyOnServer ? null : audioPath 
        })
      });
    } catch (e) {
      alert("Failed to start build");
      setProjectStatus('idle'); // Откат при ошибке
    }
  };

  const openProjectFolder = () => {
    // Формируем путь (примерно, точный путь знает бэкенд, но мы можем отправить событие на открытие)
    // Лучше всего, если бэк вернет полный путь.
    // Пока сделаем хак: запросим путь у бэка в get_project_details, но для MVP:
    // Мы знаем, где лежат проекты.
    // Но проще сделать через ipcRenderer, если мы знаем путь.
    // Давай пока просто заглушку, или передадим путь в пропсах project
    if (project.path) {
        ipcRenderer.send('open-folder', project.path + "/output"); 
    }
  };
  
  // Handlers выбора аудио/видео (оставил скрытыми для краткости, они те же)
  const handleBrowseAudio = () => ipcRenderer.send('open-audio-dialog');
  useEffect(() => {
    ipcRenderer.on('selected-audio', (e, p) => { setAudioPath(p); setAudioReadyOnServer(false); });
    return () => ipcRenderer.removeAllListeners('selected-audio');
  }, []);


  // === RENDER ===
  return (
    <div className="h-full flex flex-col bg-background">
      <SourceSelector 
        isOpen={isSelectorOpen} 
        onClose={() => setIsSelectorOpen(false)}
        alreadySelected={sources}
        onConfirm={setSources}
      />

      <header className="px-8 py-6 border-b border-border flex items-center gap-4 bg-surface">
        <button onClick={onBack} className="p-2 hover:bg-zinc-800 rounded-lg text-muted hover:text-white">
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-white">{project.name}</h1>
          <p className="text-xs text-muted flex items-center gap-2">
             <span className={`w-2 h-2 rounded-full 
                ${projectStatus === 'building' ? 'bg-yellow-500 animate-pulse' : 
                  projectStatus === 'ready' ? 'bg-green-500' : 'bg-zinc-500'}`}>
             </span>
             {projectStatus === 'building' ? 'Processing...' : projectStatus === 'ready' ? 'Build Complete' : 'Draft'}
          </p>
        </div>
      </header>

      <div className="flex-1 p-8 grid grid-cols-1 lg:grid-cols-2 gap-8 overflow-y-auto min-h-0">
        
        {/* LEFT: SOURCES (Блокируем если идет билд) */}
        <section className={projectStatus === 'building' ? 'opacity-50 pointer-events-none' : ''}>
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
              <Film className="text-purple-500" size={20} /> Sources
            </h3>
            <button onClick={() => setIsSelectorOpen(true)} className="text-xs bg-zinc-800 hover:bg-zinc-700 text-white px-3 py-1.5 rounded-md border border-zinc-700">
              + Add Movie
            </button>
          </div>
          <div className="space-y-3">
            {sources.length === 0 ? <p className="text-zinc-500 text-sm">No movies selected.</p> : 
              sources.map(alias => (
                <div key={alias} className="flex items-center justify-between p-3 bg-surface border border-border rounded-lg">
                  <span className="font-medium text-sm text-gray-300 ml-2">{alias}</span>
                  <button onClick={() => setSources(s => s.filter(i => i !== alias))} className="text-zinc-600 hover:text-red-400 p-2"><Trash2 size={16} /></button>
                </div>
              ))
            }
          </div>
        </section>

        {/* RIGHT: ACTION AREA */}
        <section className="space-y-8">
          
          {/* Audio (Блокируем если идет билд) */}
          <div className={projectStatus === 'building' ? 'opacity-50 pointer-events-none' : ''}>
            <h3 className="text-lg font-semibold text-gray-200 flex items-center gap-2 mb-4">
              <Music className="text-pink-500" size={20} /> Reference Audio
            </h3>
            <div className={`bg-surface border ${audioReadyOnServer ? 'border-green-500/30 bg-green-500/5' : 'border-border'} rounded-xl p-5`}>
              <div className="flex gap-2">
                 <input type="text" value={audioPath} readOnly placeholder="Select music file..." className="w-full bg-zinc-900 border border-zinc-700 rounded-lg p-3 text-sm text-gray-300 pl-10" />
                 <div className="absolute ml-3 mt-3">{audioReadyOnServer ? <CheckCircle size={16} className="text-green-500" /> : <Music size={16} className="text-zinc-500" />}</div>
                 <button onClick={handleBrowseAudio} className="bg-zinc-800 hover:bg-zinc-700 text-white px-4 rounded-lg border border-zinc-600"><FolderOpen size={18} /></button>
              </div>
            </div>
          </div>

          {/* BUILD / STATUS CARD */}
          <div className="bg-gradient-to-br from-zinc-900 to-black border border-zinc-800 rounded-xl p-6 relative overflow-hidden h-full max-h-[420px] flex flex-col items-center justify-center text-center">
            
            {projectStatus === 'building' && (
                <div className="py-4 animate-in fade-in zoom-in flex flex-col items-center justify-center w-full">
                    <CircularProgress percent={buildPercent} size={120} strokeWidth={6} />
                    <h4 className="mt-6 text-white font-medium text-lg animate-pulse text-center">
                        {buildText}
                    </h4>
                    <p className="text-zinc-500 text-sm mt-1">
                        Do not close the application.
                    </p>
                </div>
                )}

            {projectStatus === 'ready' && (
               <div className="py-4 animate-in fade-in zoom-in">
                  <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mb-4 mx-auto border border-green-500/50 shadow-[0_0_20px_rgba(34,197,94,0.3)]">
                    <CheckCircle className="text-green-500" size={40} />
                  </div>
                  <h3 className="text-xl font-bold text-white">Assembly Complete!</h3>
                  <p className="text-zinc-400 text-sm mb-6">Your XML timeline is ready for export.</p>
                  
                  <div className="flex flex-col gap-3 w-full max-w-xs mx-auto">
                      <button 
                        onClick={openProjectFolder}
                        className="w-full bg-zinc-800 hover:bg-zinc-700 text-white font-medium py-3 rounded-lg border border-zinc-600 flex items-center justify-center gap-2 transition-colors"
                      >
                        <Folder size={18} /> Open Output Folder
                      </button>
                      
                      <button 
                        onClick={() => setProjectStatus('idle')} // Сброс, чтобы собрать заново
                        className="text-xs text-zinc-500 hover:text-zinc-300 mt-2 underline"
                      >
                        Start New Assembly
                      </button>
                  </div>
               </div>
            )}

            {projectStatus === 'idle' && (
               <div className="animate-in fade-in">
                  <div className="w-16 h-16 bg-gradient-to-tr from-purple-600 to-blue-600 rounded-full flex items-center justify-center mb-4 mx-auto shadow-lg shadow-purple-900/30">
                    <Wand2 className="text-white" size={32} />
                  </div>
                  <h3 className="text-xl font-bold text-white">Ready to Assemble?</h3>
                  <p className="text-zinc-400 text-sm mb-6 max-w-xs mx-auto">
                    Sculptor will analyze {sources.length} movies and sync them to your audio track.
                  </p>
                  
                  <button 
                    onClick={handleStartBuild}
                    disabled={sources.length === 0 || (!audioPath && !audioReadyOnServer)}
                    className="w-full bg-white text-black hover:bg-gray-200 font-bold py-3 rounded-lg transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 px-8"
                  >
                    <Wand2 size={18} />
                    {audioReadyOnServer ? "Re-Assemble" : "Start Assembly"}
                  </button>
               </div>
            )}
            
          </div>
        </section>
      </div>
    </div>
  );
}