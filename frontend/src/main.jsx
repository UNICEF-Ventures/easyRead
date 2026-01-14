import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css' // Import global styles
import { AuthProvider, TokenProvider } from './auth/auth.js'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <TokenProvider>
          <App />
      </TokenProvider>
      </AuthProvider>
  </React.StrictMode>,
)
