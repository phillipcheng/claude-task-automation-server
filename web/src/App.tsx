import React, { useState } from 'react';
import Tasks from './components/Tasks';
import Chat from './components/Chat';
import Projects from './components/Projects';
import './styles/App.css';

type TabType = 'tasks' | 'chat' | 'projects';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('tasks');

  const renderContent = () => {
    switch (activeTab) {
      case 'tasks':
        return <Tasks />;
      case 'chat':
        return <Chat />;
      case 'projects':
        return <Projects />;
      default:
        return <Tasks />;
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Task Automation</h1>
        <nav className="app-nav">
          <button
            className={`nav-tab ${activeTab === 'tasks' ? 'active' : ''}`}
            onClick={() => setActiveTab('tasks')}
          >
            Tasks
          </button>
          <button
            className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            Chat
          </button>
          <button
            className={`nav-tab ${activeTab === 'projects' ? 'active' : ''}`}
            onClick={() => setActiveTab('projects')}
          >
            Projects
          </button>
        </nav>
      </header>
      <main className="app-content">
        {renderContent()}
      </main>
    </div>
  );
};

export default App;
