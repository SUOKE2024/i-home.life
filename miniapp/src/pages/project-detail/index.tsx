import React, { useState, useCallback } from 'react';
import { View, Text, Image, Button } from '@tarojs/components';
import Taro, { useRouter, usePullDownRefresh, useDidShow } from '@tarojs/taro';
import classnames from 'classnames';
import SectionHeader from '@/components/SectionHeader';
import StatusTag from '@/components/StatusTag';
import ProgressBar from '@/components/ProgressBar';
import { callFunction } from '@/services/cloud';
import {
  PROJECT_STAGE_LABEL,
  PROJECT_STAGE_ORDER,
  projectStatusLabel,
  stageIndexOf
} from '@/types/project';
import type { RenovationProject } from '@/types/project';
import styles from './index.module.scss';

const ProjectDetailPage: React.FC = () => {
  const router = useRouter();
  const routeId = router.params.id || '';
  const [project, setProject] = useState<RenovationProject | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  const loadProject = useCallback(async () => {
    try {
      const data = await callFunction<{ projects: RenovationProject[] }>('getProjects');
      // 带了 id 就必须命中那一条：回落「第一个未交付项目」会让业主打开别人的项目档案
      const found = routeId
        ? data.projects.find((item) => item.id === routeId) || null
        : data.projects.find((item) => !item.delivered) || data.projects[0] || null;
      console.info('[ProjectDetailPage] 项目详情加载成功', { routeId, found: found?.id });
      setProject(found);
      setError(
        found ? '' : routeId ? '该项目不存在或无权查看' : '暂无可查看的改造项目'
      );
    } catch (err) {
      console.error('[ProjectDetailPage] 项目详情加载失败', err);
      setError('加载失败，请稍后重试');
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [routeId]);

  useDidShow(() => {
    loadProject();
  });

  usePullDownRefresh(() => {
    loadProject();
  });

  if (loading && !project) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在加载项目档案…</Text>
      </View>
    );
  }

  if (error || !project) {
    return (
      <View className={styles.page}>
        <View className={styles.errorCard}>
          <Text className={styles.errorText}>{error || '暂无可查看的改造项目'}</Text>
          <Button className={styles.retryButton} onClick={loadProject}>
            重新加载
          </Button>
        </View>
      </View>
    );
  }

  const currentIndex = stageIndexOf(project.stage);

  return (
    <View className={styles.page}>
      <View className={styles.coverWrap}>
        <Image className={styles.cover} src={project.cover} mode='aspectFill' />
        <View className={styles.coverMask} />
        <View className={styles.coverContent}>
          <Text className={styles.coverTitle}>{project.name}</Text>
          <Text className={styles.coverSub}>{project.spaceName}</Text>
        </View>
      </View>

      <View className={styles.summaryCard}>
        <View className={styles.summaryHead}>
          <StatusTag
            text={project.delivered ? '已交付' : projectStatusLabel(project)}
            tone={project.delivered ? 'green' : 'gold'}
          />
          <Text className={styles.progressValue}>{project.progress}%</Text>
        </View>
        <ProgressBar percent={project.progress} tone={project.delivered ? 'green' : 'gold'} />
        <Text className={styles.milestone}>
          {project.pending
            ? `下一步：${project.nextMilestone}`
            : `下一节点：${project.nextMilestone} · ${project.nextDate}`}
        </Text>
      </View>

      <SectionHeader title='交付进度' subtitle='六阶段透明化交付' />
      <View className={styles.card}>
        <View className={styles.steps}>
          {PROJECT_STAGE_ORDER.map((stage, index) => {
            // 待勘测项目还没进六阶段，不能把「设计」点亮成进行中
            const done = project.delivered || (!project.pending && index < currentIndex);
            const active = !project.pending && !project.delivered && index === currentIndex;
            return (
              <View key={stage} className={styles.stepItem}>
                <View
                  className={classnames(
                    styles.stepDot,
                    done && styles.stepDotDone,
                    active && styles.stepDotActive
                  )}
                >
                  <Text className={styles.stepDotText}>{done ? '✓' : index + 1}</Text>
                </View>
                <Text
                  className={classnames(
                    styles.stepLabel,
                    done && styles.stepLabelDone,
                    active && styles.stepLabelActive
                  )}
                >
                  {PROJECT_STAGE_LABEL[stage]}
                </Text>
              </View>
            );
          })}
        </View>
      </View>

      <SectionHeader title='项目档案' />
      <View className={styles.card}>
        <View className={styles.infoRow}>
          <Text className={styles.infoLabel}>当前阶段</Text>
          <Text className={styles.infoValue}>{projectStatusLabel(project)}</Text>
        </View>
        <View className={styles.infoRow}>
          <Text className={styles.infoLabel}>施工方</Text>
          <Text className={styles.infoValue}>{project.contractor}</Text>
        </View>
        <View className={styles.infoRow}>
          <Text className={styles.infoLabel}>合同预算</Text>
          <Text className={styles.infoValue}>{project.budget}</Text>
        </View>
        <View className={styles.infoRow}>
          <Text className={styles.infoLabel}>最近更新</Text>
          <Text className={styles.infoValue}>{project.updatedAt}</Text>
        </View>
      </View>

      <View className={styles.notice}>
        <Text className={styles.noticeText}>
          交付节点与预算以签约合同及现场验收记录为准，平台按实际进度同步，不做提前承诺。
        </Text>
      </View>

      <View className={styles.actions}>
        <Button className={styles.ghostButton} onClick={() => Taro.navigateTo({ url: '/pages/ai-consult/index' })}>
          AI 管家咨询
        </Button>
        <Button className={styles.primaryButton} onClick={() => Taro.switchTab({ url: '/pages/project/index' })}>
          返回项目列表
        </Button>
      </View>
    </View>
  );
};

export default ProjectDetailPage;
