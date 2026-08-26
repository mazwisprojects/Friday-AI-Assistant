import React, { useState, useEffect } from 'react';
import { Code, Play, Save, FolderOpen, X, FileCode, Copy, Trash2 } from 'lucide-react';

export default function CodeWindow({ position, onClose, onDrag }) {
  const [code, setCode] = useState('');
  const [language, setLanguage] = useState('python');
  const [output, setOutput] = useState('');
  const [snippets, setSnippets] = useState([]);

  useEffect(() => {
    const socket = window.socket;
    
    socket.on('code_output', (data) => {
      setOutput(data);
    });
    
    socket.on('code_snippets', (data) => {
      setSnippets(data);
    });
    
    socket.emit('get_code_snippets');
    
    return () => {
      socket.off('code_output');
      socket.off('code_snippets');
    };
  }, []);

  const handleRun = () => {
    window.socket.emit('run_code', { code, language });
  };

  const handleSave = () => {
    window.socket.emit('save_code', { code, language });
  };

  const handleLoadSnippet = (snippet) => {
    setCode(snippet.code);
    setLanguage(snippet.language);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
  };

  return (
    <div 
      className="window code-window"
      style={{ 
        transform: `translate(${position.x}px, ${position.y}px)`,
        width: '600px',
        height: '500px'
      }}
    >
      <div className="window-header" onMouseDown={onDrag}>
        <div className="window-title">
          <Code size={16} />
          <span>Code Helper</span>
        </div>
        <button className="window-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>
      <div className="window-content">
        <div className="code-toolbar">
          <select 
            value={language} 
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="html">HTML</option>
            <option value="css">CSS</option>
          </select>
          <button onClick={handleRun}>
            <Play size={14} />
            Run
          </button>
          <button onClick={handleSave}>
            <Save size={14} />
            Save
          </button>
          <button onClick={handleCopy}>
            <Copy size={14} />
            Copy
          </button>
        </div>

        <div className="code-editor">
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Write your code here..."
            spellCheck="false"
          />
        </div>

        {output && (
          <div className="code-output">
            <h4>Output</h4>
            <pre>{output}</pre>
          </div>
        )}

        {snippets.length > 0 && (
          <div className="code-snippets">
            <div className="snippets-header">
              <FolderOpen size={14} />
              <span>Snippets</span>
            </div>
            {snippets.map((snippet, index) => (
              <div 
                key={index} 
                className="snippet-item"
                onClick={() => handleLoadSnippet(snippet)}
              >
                <FileCode size={14} />
                <span>{snippet.name}</span>
                <span className="snippet-lang">{snippet.language}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
