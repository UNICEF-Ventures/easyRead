import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css' // Import global styles

const AppWrapper = () => (
  <>
    {import.meta?.env?.MODE === "development" || process.env.NODE_ENV === "development" ? (
      <App
        accessToken={import.meta.env.VITE_PDF_CONVERTER_TOKEN}
        user={{
          email: `${import.meta.env.VITE_PDF_CONVERTER_EMAIL}`
        }}
      />) : <React.StrictMode>
      <App
        accessToken={import.meta.env.VITE_PDF_CONVERTER_TOKEN}
        user={{
          email: `${import.meta.env.VITE_PDF_CONVERTER_EMAIL}`
        }}
      /></React.StrictMode>}
  </>
)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppWrapper />
  </React.StrictMode>,
)
