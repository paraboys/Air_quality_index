import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css'; // This might be there or not depending on your setup
import App from './App';
// The two lines you deleted should be gone here

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// The 'reportWebVitals();' line should be gone here
