import { useState, useEffect, useCallback } from 'react';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    setIsAuthenticated(localStorage.getItem('adcast_auth') === 'true');
  }, []);

  const login = useCallback((username: string, password: string) => {
    if (username && password) {
      localStorage.setItem('adcast_auth', 'true');
      setIsAuthenticated(true);
      return true;
    }
    return false;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('adcast_auth');
    setIsAuthenticated(false);
  }, []);

  return { isAuthenticated, login, logout };
}

export default useAuth;
