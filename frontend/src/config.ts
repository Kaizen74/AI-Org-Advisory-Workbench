// Central feature flags.
//
// Simulation (Scenario Studio + Transition Planner, and their scenario/transition deliverables)
// is parked (D17/D21) to keep the app focused on org-metric compute, the Workflow Mapper, and
// Task Intelligence (external benchmarking + editing/validation). The backend generators and routes
// remain intact — flip this single flag to true to restore every simulation surface at once.
export const SHOW_SIMULATION: boolean = false;
