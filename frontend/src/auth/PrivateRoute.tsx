import React, { useContext, useEffect, useState } from "react";
import { AuthContext, useAuth } from "../auth/auth";
import { CircularProgress } from "@mui/material";

export const PrivateRoute = ({ children }) => {
  const {
    user,
    isLoading: loading,
    loginWithRedirect: login,
    getAccessTokenSilently,
    logout
  } = useAuth();

  const [error, setError] = useState<null | string>(null);

  useEffect(() => {
    const load = async () => {
      if (!user && !loading) {
        await login();
      }
    }
    load();
  }, [user, loading]);

  const { isAuthenticated } = useAuth();
  const { storeAccessToken, accessTokenExists} = useContext(AuthContext);

  useEffect(() => {
    const fetchToken = async () => {
      if (isAuthenticated && !accessTokenExists()) {
        try {
          const token = await getAccessTokenSilently();
          storeAccessToken(token);
        } catch (error) {
          console.error("Error fetching access token:", error);
          setError('Could not login in properly. try again!');
          await logout();
        }
      }
    };

    fetchToken();
  }, [isAuthenticated]);

  if (!isAuthenticated || loading || !accessTokenExists()) return <CircularProgress />;

  return user ? children : null;
};