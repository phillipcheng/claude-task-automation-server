import React, { useState } from 'react';
import Tasks from './components/Tasks';
import Projects from './components/Projects';
import './styles/App.css';

type TabType = 'tasks' | 'projects';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('tasks');

  const renderContent = () => {
    switch (activeTab) {
      case 'tasks':
        return <Tasks />;
      case 'projects':
        return <Projects />;
      default:
        return <Tasks />;
    }
  };

  return (
    <div className="app">
      {/* Floating navigation */}
      <nav className="floating-nav">
        <button
          className={`floating-nav-btn ${activeTab === 'tasks' ? 'active' : ''}`}
          onClick={() => setActiveTab('tasks')}
          title="Tasks"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
          </svg>
        </button>
        <button
          className={`floating-nav-btn ${activeTab === 'projects' ? 'active' : ''}`}
          onClick={() => setActiveTab('projects')}
          title="Projects"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
          </svg>
        </button>
      </nav>
      <main className="app-content">
        {renderContent()}
      </main>
    </div>
  );
};

export default App;
