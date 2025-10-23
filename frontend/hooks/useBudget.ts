import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { BudgetInfo, BudgetsSummary } from '@/types/budget';

interface UseBudgetReturn {
  // State
  globalBudget: BudgetInfo | null;
  sessionBudget: BudgetInfo | null;
  budgetsSummary: BudgetsSummary | null;
  loading: boolean;
  error: string | null;

  // Actions
  loadGlobalBudget: () => Promise<void>;
  loadSessionBudget: (sessionId: string) => Promise<void>;
  loadBudgetsSummary: () => Promise<void>;
  updateGlobalBudget: (limit: number) => Promise<void>;
  updateSessionBudget: (sessionId: string, limit: number) => Promise<void>;
}

export function useBudget(
  sessionId?: string,
  autoLoad: boolean = true
): UseBudgetReturn {
  const [globalBudget, setGlobalBudget] = useState<BudgetInfo | null>(null);
  const [sessionBudget, setSessionBudget] = useState<BudgetInfo | null>(null);
  const [budgetsSummary, setBudgetsSummary] = useState<BudgetsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load global budget
  const loadGlobalBudget = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const budget = await api.getGlobalBudget();
      setGlobalBudget(budget);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load global budget';
      setError(errorMessage);
      console.error('Error loading global budget:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load session budget
  const loadSessionBudget = useCallback(async (sessionId: string) => {
    try {
      setLoading(true);
      setError(null);
      const budget = await api.getSessionBudget(sessionId);
      setSessionBudget(budget);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load session budget';
      setError(errorMessage);
      console.error('Error loading session budget:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load budgets summary
  const loadBudgetsSummary = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const summary = await api.getBudgetsSummary();
      setBudgetsSummary(summary);
      setGlobalBudget(summary.global_budget);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load budgets summary';
      setError(errorMessage);
      console.error('Error loading budgets summary:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Update global budget
  const updateGlobalBudget = useCallback(async (limit: number) => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.updateGlobalBudget(limit);
      setGlobalBudget(response.budget);

      // Reload summary if it was loaded
      if (budgetsSummary) {
        await loadBudgetsSummary();
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update global budget';
      setError(errorMessage);
      console.error('Error updating global budget:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [budgetsSummary, loadBudgetsSummary]);

  // Update session budget
  const updateSessionBudget = useCallback(async (sessionId: string, limit: number) => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.updateSessionBudget(sessionId, limit);
      setSessionBudget(response.budget);

      // Reload summary if it was loaded
      if (budgetsSummary) {
        await loadBudgetsSummary();
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update session budget';
      setError(errorMessage);
      console.error('Error updating session budget:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [budgetsSummary, loadBudgetsSummary]);

  // Auto-load on mount if requested
  useEffect(() => {
    if (autoLoad) {
      loadGlobalBudget();
    }
  }, [autoLoad, loadGlobalBudget]);

  // Load session budget whenever sessionId changes
  useEffect(() => {
    if (autoLoad && sessionId) {
      loadSessionBudget(sessionId);
    }
  }, [autoLoad, sessionId, loadSessionBudget]);

  return {
    globalBudget,
    sessionBudget,
    budgetsSummary,
    loading,
    error,
    loadGlobalBudget,
    loadSessionBudget,
    loadBudgetsSummary,
    updateGlobalBudget,
    updateSessionBudget,
  };
}
