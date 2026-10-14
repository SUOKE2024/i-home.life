export type ProjectStage = 'design' | 'budget' | 'procurement' | 'construction' | 'qa' | 'settlement';

export interface RenovationProject {
  id: string;
  name: string;
  spaceName: string;
  cover: string;
  stage: ProjectStage;
  progress: number;
  nextMilestone: string;
  nextDate: string;
  contractor: string;
  budget: string;
  delivered: boolean;
  updatedAt: string;
}

export const PROJECT_STAGE_ORDER: ProjectStage[] = [
  'design',
  'budget',
  'procurement',
  'construction',
  'qa',
  'settlement'
];

export const PROJECT_STAGE_LABEL: Record<ProjectStage, string> = {
  design: '设计',
  budget: '预算',
  procurement: '采购',
  construction: '施工',
  qa: '质检',
  settlement: '结算'
};

export const stageIndexOf = (stage: ProjectStage): number => PROJECT_STAGE_ORDER.indexOf(stage);