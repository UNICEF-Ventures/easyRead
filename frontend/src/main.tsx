import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css' // Import global styles

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App 
      token={import.meta.env.VITE_PDF_CONVERTER_TOKEN}
      apiKey={import.meta.env.VITE_PDF_CONVERTER_API_KEY || 'not-used'}
      email={import.meta.env.VITE_PDF_CONVERTER_EMAIL} 
      />
  </React.StrictMode>,
)
