import { useState } from 'react';
import { Film, LayoutTemplate } from 'lucide-react'; // Scissors удален, так как Editor мы убрали
import { Library } from './components/Library';
import { Projects } from './components/Projects';
import { ProjectDetail } from './components/ProjectDetail';

function App() {
  const [activeTab, setActiveTab] = useState('projects');
  const [selectedProject, setSelectedProject] = useState(null);

  const renderContent = () => {
    if (selectedProject) {
      return (
        <ProjectDetail 
          project={selectedProject} 
          onBack={() => setSelectedProject(null)} 
        />
      );
    }

    switch (activeTab) {
      case 'library':
        return <Library />;
      case 'projects':
        return <Projects onOpenProject={(proj) => setSelectedProject(proj)} />;
      default:
        return <Projects onOpenProject={(proj) => setSelectedProject(proj)} />;
    }
  };

  const getNavClass = (tabName) => {
    const base = "flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ";
    if (activeTab === tabName) {
      return base + "bg-accent/10 text-accent shadow-[0_0_15px_rgba(59,130,246,0.1)] border border-accent/20";
    }
    return base + "text-muted hover:bg-white/5 hover:text-gray-200";
  };

  return (
    // ROOT CONTAINER:
    // flex = выстраиваем детей (Sidebar + Main) в ряд
    // h-screen = высота ровно в экран
    // w-screen = ширина ровно в экран
    // overflow-hidden = никаких скроллов на уровне окна
    <div className="flex h-screen w-screen bg-background text-primary overflow-hidden">
      
      {/* SIDEBAR (Скрываем, если открыт проект) */}
      {!selectedProject && (
        // w-64 = фиксированная ширина
        // flex-shrink-0 = запрещаем сжиматься, если места мало
        <aside className="w-64 flex-shrink-0 bg-surface border-r border-border flex flex-col z-10 shadow-xl">
          <div className="p-6">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              <span className="text-accent">◆</span> SCULPTOR PRO
            </h1>
          </div>
          
          <nav className="flex-1 px-4 space-y-2">
            <button onClick={() => setActiveTab('library')} className={getNavClass('library')}>
              <Film size={18} /> Library
            </button>
            <button onClick={() => setActiveTab('projects')} className={getNavClass('projects')}>
              <LayoutTemplate size={18} /> Projects
            </button>
          </nav>

          <div className="p-4 border-t border-border bg-black/20">
            <div className="flex items-center gap-2 text-xs text-muted">
              <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
              Core Online: localhost:8000
            </div>
          </div>
        </aside>
      )}

      {/* MAIN CONTENT AREA */}
      {/* flex-1 = занимай ВСЁ оставшееся пространство (растянись вправо) */}
      {/* flex + flex-col = чтобы внутри контент (ProjectDetail) тоже мог растягиваться по высоте */}
      {/* min-w-0 = критически важно для flex-контейнеров, чтобы контент не вылезал */}
      <main className="flex-1 flex flex-col h-full relative overflow-hidden min-w-0">
        
        {/* Фоновый градиент только на дашборде */}
        {!selectedProject && (
           <div className="absolute top-0 left-0 w-full h-96 bg-accent/5 rounded-full blur-3xl -translate-y-1/2 pointer-events-none"></div>
        )}
        
        {/* Само содержимое (Library, Projects или Detail) */}
        {renderContent()}
        
      </main>
    </div>
  );
}

export default App;