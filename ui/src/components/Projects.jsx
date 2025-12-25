import { useState, useEffect, useCallback } from 'react';
import { LayoutTemplate, Folder, Calendar, Plus, Trash2 } from 'lucide-react';
import { CreateProjectModal } from './CreateProjectModal';

export function Projects({ onOpenProject }) {
  const [projects, setProjects] = useState([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // Состояние для контекстного меню: { x, y, project } или null
  const [contextMenu, setContextMenu] = useState(null); 

  const fetchProjects = useCallback(() => {
    fetch('http://localhost:8000/projects')
      .then(res => {
         if (!res.ok) throw new Error("Err");
         return res.json();
      })
      .then(data => setProjects(data))
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Закрываем меню при клике в любое место
  useEffect(() => {
    const handleClick = () => setContextMenu(null);
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, []);

  // Обработчик ПКМ (Правой Кнопки Мыши)
  const handleContextMenu = (e, project) => {
    e.preventDefault(); // Блокируем стандартное меню браузера
    e.stopPropagation(); // Чтобы клик не ушел выше
    
    setContextMenu({
      x: e.pageX,
      y: e.pageY,
      project: project
    });
  };

  const handleDelete = async (projectName) => {
    // Спрашиваем подтверждение
    if (!confirm(`Are you sure you want to delete "${projectName}"?`)) return;

    try {
      await fetch(`http://localhost:8000/projects/${projectName}`, { method: 'DELETE' });
      fetchProjects(); // Обновляем список
    } catch (e) {
      alert("Failed to delete project");
    }
  };

  return (
    <div className="p-8 h-full overflow-y-auto relative min-h-screen">
      
      <CreateProjectModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onSuccess={fetchProjects}
      />

      {/* === КОНТЕКСТНОЕ МЕНЮ (Рендерим только если оно есть) === */}
      {contextMenu && (
        <div 
          className="fixed z-50 bg-zinc-800 border border-zinc-700 shadow-xl rounded-lg py-1 min-w-[160px] animate-in fade-in zoom-in-95 duration-100"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={(e) => e.stopPropagation()} // Чтобы клик по меню не закрывал его сразу
        >
          <div className="px-3 py-2 text-xs text-zinc-500 border-b border-zinc-700 mb-1">
             {contextMenu.project.name}
          </div>
          <button 
            onClick={() => {
                handleDelete(contextMenu.project.name);
                setContextMenu(null);
            }}
            className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 flex items-center gap-2 transition-colors"
          >
            <Trash2 size={14} /> Delete Project
          </button>
        </div>
      )}

      {/* HEADER */}
      <header className="mb-8 flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold text-primary">Projects</h2>
          <p className="text-muted text-sm mt-1">Your editing workspaces</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg shadow-purple-900/20 flex items-center gap-2"
        >
          <Plus size={16} /> New Project
        </button>
      </header>

      {/* GRID */}
      {projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 border border-dashed border-zinc-800 rounded-xl bg-zinc-900/20">
          <div className="w-16 h-16 bg-zinc-800 rounded-full flex items-center justify-center mb-4">
            <LayoutTemplate className="w-8 h-8 text-zinc-600" />
          </div>
          <h3 className="text-lg font-medium text-zinc-300">No projects yet</h3>
          <p className="text-zinc-500 text-sm mt-1 mb-6">Create your first project to start editing.</p>
          <button 
             onClick={() => setIsModalOpen(true)}
             className="text-purple-400 hover:text-purple-300 text-sm font-medium hover:underline"
          >
            Create New Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-20">
          {projects.map((proj) => (
            <div 
              key={proj.name} 
              onClick={() => onOpenProject(proj)}
              onContextMenu={(e) => handleContextMenu(e, proj)}
              className="group bg-surface border border-border p-5 rounded-xl hover:border-purple-500/50 hover:bg-zinc-900 transition-all cursor-pointer relative shadow-sm hover:shadow-purple-900/10"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-10 h-10 bg-zinc-800 rounded-lg flex items-center justify-center group-hover:bg-purple-500/10 group-hover:text-purple-400 transition-colors">
                  <Folder size={20} />
                </div>
              </div>

              <h3 className="font-bold text-lg text-gray-200 group-hover:text-white transition-colors truncate pr-2">
                {proj.name}
              </h3>
              
              <div className="mt-4 flex items-center gap-4 text-xs text-muted">
                <div className="flex items-center gap-1.5">
                  <Calendar size={12} />
                  <span>Local Project</span> 
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}