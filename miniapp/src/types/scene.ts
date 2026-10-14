export type SceneType = 'manual' | 'scheduled' | 'triggered' | 'geo';

export interface SceneAutomation {
  id: string;
  spaceId: string;
  name: string;
  sceneType: SceneType;
  sceneTypeLabel: string;
  trigger: string;
  actions: string;
  enabled: boolean;
  lastExecutedAt: string;
}

export interface ExecuteSceneResult {
  sceneId: string;
  executed: boolean;
  executedAt: string;
}