export type NodeState = 'idle' | 'queued' | 'active' | 'done' | 'failed'

export interface GraphNode {
  id: string
  label: string
  stepName?: string // agent_results step name that drives this node
  x: number
  y: number
  group: string
  kind?: 'start' | 'end' | 'gate' | 'loop' | 'fail'
  width?: number
}

export interface GraphEdge {
  from: string
  to: string
  label?: string
  loop?: boolean
  dashed?: boolean
}

export interface Band {
  id: string
  label: string
  y0: number
  y1: number
  accent: string
}

export const NODE_W = 168
export const NODE_H = 50

const N = (id: string, label: string, x: number, y: number, group: string, extra: Partial<GraphNode> = {}): GraphNode => ({
  id,
  label,
  stepName: id,
  x,
  y,
  group,
  ...extra,
})

export const NODES: GraphNode[] = [
  N('start', 'Request', 565, 28, 'g0', { kind: 'start', stepName: undefined, width: 96 }),
  N('validate', 'Validate', 565, 92, 'g0', { stepName: 'data_validation' }),
  N('maintenance', 'Maintenance', 240, 216, 'g1'),
  N('traffic', 'Traffic', 565, 216, 'g1'),
  N('priority', 'Priority', 890, 216, 'g1'),
  N('merge', 'Merge', 565, 344, 'g1', { width: 118 }),
  N('historical', 'Historical', 565, 436, 'g2'),
  N('rag', 'RAG Retrieve', 565, 522, 'g2'),
  N('web_research', 'Web Research', 565, 608, 'g2', { stepName: 'web_research' }),
  N('evidence', 'Evidence Check', 565, 694, 'g2', { stepName: 'evidence_validation' }),
  N('candidate', 'Candidates', 565, 790, 'g3'),
  N('optimize', 'CP-SAT', 565, 884, 'g4', { kind: 'gate' }),
  N('simulate', 'Simulate', 565, 970, 'g4'),
  N('routing', 'Routing', 565, 1056, 'g4'),
  N('route_optimize', 'Route Optimizer', 565, 1142, 'g4'),
  N('gate', 'Hard-Conflict Gate', 565, 1240, 'g5', { kind: 'gate' }),
  N('validate_constraints', 'Constraint Validation', 565, 1332, 'g5', { kind: 'loop' }),
  N('risk', 'Risk Agent', 565, 1432, 'g6'),
  N('fusion', 'Decision Fusion', 565, 1518, 'g6'),
  N('report', 'Report', 565, 1604, 'g6', { stepName: 'report' }),
  N('end', 'END', 565, 1670, 'g6', { kind: 'end', stepName: undefined, width: 96 }),
  N('fail', 'FAIL', 915, 1332, 'g5', { kind: 'fail' }),
]

export const EDGES: GraphEdge[] = [
  { from: 'start', to: 'validate' },
  { from: 'validate', to: 'maintenance', dashed: true, label: 'router' },
  { from: 'validate', to: 'traffic', dashed: true },
  { from: 'validate', to: 'priority', dashed: true },
  { from: 'maintenance', to: 'merge' },
  { from: 'traffic', to: 'merge' },
  { from: 'priority', to: 'merge' },
  { from: 'merge', to: 'historical' },
  { from: 'historical', to: 'rag' },
  { from: 'rag', to: 'web_research' },
  { from: 'web_research', to: 'evidence' },
  { from: 'evidence', to: 'candidate' },
  { from: 'candidate', to: 'optimize' },
  { from: 'optimize', to: 'simulate' },
  { from: 'optimize', to: 'fail', dashed: true, label: 'no solution' },
  { from: 'simulate', to: 'routing' },
  { from: 'routing', to: 'route_optimize' },
  { from: 'route_optimize', to: 'gate' },
  { from: 'gate', to: 'validate_constraints' },
  { from: 'gate', to: 'candidate', loop: true, label: 'retry ≤3' },
  { from: 'gate', to: 'fail', dashed: true },
  { from: 'validate_constraints', to: 'risk' },
  { from: 'validate_constraints', to: 'candidate', loop: true, label: 'regenerate' },
  { from: 'validate_constraints', to: 'fail', dashed: true },
  { from: 'risk', to: 'fusion' },
  { from: 'fusion', to: 'report' },
  { from: 'report', to: 'end' },
]

export const BANDS: Band[] = [
  { id: 'g0', label: 'Input & Validation', y0: 18, y1: 132, accent: '#1D5FA7' },
  { id: 'g1', label: 'Perception Agents', y0: 178, y1: 400, accent: '#123B66' },
  { id: 'g2', label: 'Knowledge & Evidence', y0: 430, y1: 750, accent: '#4B5563' },
  { id: 'g3', label: 'Plan Synthesis', y0: 762, y1: 830, accent: '#1D5FA7' },
  { id: 'g4', label: 'Deterministic Engine', y0: 858, y1: 1180, accent: '#18794E' },
  { id: 'g5', label: 'Assurance Loops', y0: 1216, y1: 1388, accent: '#A15C00' },
  { id: 'g6', label: 'Governance & Output', y0: 1410, y1: 1700, accent: '#B3261E' },
]

export const PHASE_OF: Record<string, string> = {
  start: 'g0', validate: 'g0',
  maintenance: 'g1', traffic: 'g1', priority: 'g1', merge: 'g1',
  historical: 'g2', rag: 'g2', web_research: 'g2', evidence: 'g2',
  candidate: 'g3',
  optimize: 'g4', simulate: 'g4', routing: 'g4', route_optimize: 'g4',
  gate: 'g5', validate_constraints: 'g5', fail: 'g5',
  risk: 'g6', fusion: 'g6', report: 'g6', end: 'g6',
}