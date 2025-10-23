/**
 * Budget Management Types
 *
 * Types for tracking global and session-level budgets.
 */

export interface BudgetInfo {
  id: string;
  type: 'global' | 'session';
  limit: number;
  spent: number;
  remaining: number;
  session_id?: string;
  session_name?: string;
  updated_at: number;
  updated_at_iso: string;
}

export interface UpdateBudgetLimitRequest {
  limit: number;
}

export interface BudgetUpdateResponse {
  success: boolean;
  budget: BudgetInfo;
  message: string;
}

export interface BudgetsSummary {
  global_budget: BudgetInfo;
  session_budgets_count: number;
  session_budgets_total_limit: number;
  session_budgets_total_spent: number;
  session_budgets: BudgetInfo[];
}
