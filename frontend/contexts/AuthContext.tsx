'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is already logged in
    const token = localStorage.getItem('auth_token');
    if (token) {
      setIsAuthenticated(true);
    }
    setIsLoading(false);
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      // Fetch credentials from public config
      const response = await fetch('/auth-config.js');
      const configText = await response.text();

      // Parse the config (it's a JS file with window.AUTH_CONFIG)
      const match = configText.match(/window\.AUTH_CONFIG\s*=\s*({[^}]+})/);
      if (!match) {
        console.error('Failed to parse auth config');
        return false;
      }

      const config = JSON.parse(match[1]);

      // Check credentials
      if (username === config.DEMO_USERNAME && password === config.DEMO_PASSWORD) {
        // Generate a simple token (in production, this would come from backend)
        const token = btoa(`${username}:${Date.now()}`);
        localStorage.setItem('auth_token', token);
        localStorage.setItem('username', username);
        setIsAuthenticated(true);
        return true;
      }

      return false;
    } catch (error) {
      console.error('Login error:', error);
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('username');
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
