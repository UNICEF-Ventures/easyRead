import React, { useState, createContext } from "react";
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import history from "./history";

const onRedirectCallback = (appState) => {
  history.push(
    appState && appState.returnTo ? appState.returnTo : window.location.pathname
  );
};

const providerConfig = {
  domain: import.meta.env.VITE_OIDC_AUTH_DOMAIN,
  clientId: import.meta.env.VITE_OIDC_CLIENT_ID,
  onRedirectCallback,
  authorizationParams: {
    redirect_uri: `${window.location.origin}`,
    audience: `${import.meta.env.VITE_OIDC_DOMAIN}/api/v2/`,
    post_logout_redirect_uri: `${window.location.origin}/logout`,
    response_type: 'code',
    scope: 'openid profile email api_scope',
  },
};



const AuthProvider = ({ children }) => {
  return (<Auth0Provider {...providerConfig}>
    {children}
  </Auth0Provider>)
}

// Create AuthContext to manage user state
const AuthContext = createContext(
  {
    accessTokenExists: () => false,
    getAccessToken: () => null,
    storeAccessToken: (token) => {},
    removeAccessToken: () => {},
  }
);

const TokenProvider = ({children}) => {
  const [accessToken, setAccessToken] = useState(null);
  const ACCESS_TOKEN_KEY = "access_token";

  const accessTokenExists = () => {
    return accessToken || !!localStorage.getItem(ACCESS_TOKEN_KEY);
  }
  
  const getAccessToken = () => {
    if(accessToken){
      return accessToken;
    }
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }
  
  const storeAccessToken = (token) => {
    setAccessToken(token);
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
  }
  
  const removeAccessToken = () => {
    setAccessToken(null);
    localStorage.removeItem(ACCESS_TOKEN_KEY);
  }

  return (
    <AuthContext.Provider value={{ accessTokenExists, storeAccessToken, getAccessToken, removeAccessToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export { useAuth0 as useAuth, AuthProvider, TokenProvider, AuthContext }