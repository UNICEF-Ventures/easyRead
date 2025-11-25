import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css' // Import global styles

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App
      accessToken={import.meta.env.VITE_PDF_CONVERTER_TOKEN}
      user={{
        email: `${import.meta.env.VITE_PDF_CONVERTER_EMAIL}`
      }}
    />
  </React.StrictMode>,
)
