/**
 * TriFlow Shared Library
 *
 * Provides reusable hooks, components, and utilities for module development.
 * Use these to eliminate repetitive code and ensure consistency across modules.
 */

// Hooks
export {
  useModuleData,
  useModuleTable,
  useModuleFilters
} from './hooks';

// Components
export {
  ModulePageLayout,
  DataTable
} from './components';

export type { DataTableColumn } from './components';
