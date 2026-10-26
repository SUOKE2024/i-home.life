export type ProjectStage = 'design' | 'budget' | 'procurement' | 'construction' | 'qa' | 'settlement';

export interface RenovationProject {
  id: string;
  name: string;
  spaceName: string;
  cover: string;
  stage: ProjectStage;
  /** 展示用阶段名：initiation（刚提交需求）显示「待勘测」，不冒充「设计」；缺省回退 stage 标签 */
  statusLabel?: string;
  /** 是否尚未进入六阶段（后端 phase=initiation，无阶段高亮） */
  pending?: boolean;
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

/** 展示用阶段名：优先 statusLabel（待勘测等后端 phase 语义），旧数据回落六阶段标签 */
export const projectStatusLabel = (project: RenovationProject): string =>
  project.statusLabel || PROJECT_STAGE_LABEL[project.stage];