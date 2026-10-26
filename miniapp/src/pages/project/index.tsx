import React, { useState, useCallback } from 'react';
import { View, Text, Image } from '@tarojs/components';
import Taro, { usePullDownRefresh, useDidShow } from '@tarojs/taro';
import classnames from 'classnames';
import SectionHeader from '@/components/SectionHeader';
import StatusTag from '@/components/StatusTag';
import ProgressBar from '@/components/ProgressBar';
import { callFunction } from '@/services/cloud';
import {
  PROJECT_STAGE_LABEL,
  PROJECT_STAGE_ORDER,
  stageIndexOf
} from '@/types/project';
import type { RenovationProject } from '@/types/project';
import styles from './index.module.scss';

const ProjectPage: React.FC = () => {
  const [projects, setProjects] = useState<RenovationProject[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadProjects = useCallback(async () => {
    try {
      const data = await callFunction<{ projects: RenovationProject[] }>('getProjects');
      console.info('[ProjectPage] 项目列表加载成功', { count: data.projects.length });
      setProjects(data.projects);
    } catch (err) {
      console.error('[ProjectPage] 项目列表加载失败', err);
      Taro.showToast({ title: '加载失败，请稍后重试', icon: 'none' });
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, []);

  useDidShow(() => {
    loadProjects();
  });

  usePullDownRefresh(() => {
    loadProjects();
  });

  const handleDetail = (project: RenovationProject) => {
    console.info('[ProjectPage] 查看项目详情', project.id);
    Taro.navigateTo({ url: `/pages/project-detail/index?id=${project.id}` });
  };

  const handleCreateDemand = () => {
    Taro.navigateTo({ url: '/pages/demand/index' });
  };

  const activeProjects = projects.filter((item) => !item.delivered);
  const deliveredProjects = projects.filter((item) => item.delivered);

  if (loading && projects.length === 0) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在加载改造项目…</Text>
      </View>
    );
  }

  return (
    <View className={styles.page}>
      <View className={styles.summaryCard}>
        <View className={styles.summaryItem}>
          <Text className={styles.summaryValue}>{activeProjects.length}</Text>
          <Text className={styles.summaryLabel}>进行中项目</Text>
        </View>
        <View className={styles.summaryDivider} />
        <View className={styles.summaryItem}>
          <Text className={styles.summaryValue}>{deliveredProjects.length}</Text>
          <Text className={styles.summaryLabel}>已交付项目</Text>
        </View>
      </View>

      <View className={styles.createCard} onClick={handleCreateDemand}>
        <View className={styles.createMain}>
          <Text className={styles.createTitle}>想改造，还没立项？</Text>
          <Text className={styles.createDesc}>提交需求后可安排上门勘测，进度在这里跟进</Text>
        </View>
        <Text className={styles.createArrow}>›</Text>
      </View>

      <SectionHeader title="进行中" subtitle="六阶段透明化交付" />
      {activeProjects.length > 0 ? (
        activeProjects.map((project) => {
          const currentIndex = project.pending ? -1 : stageIndexOf(project.stage);
          return (
            <View key={project.id} className={styles.projectCard} onClick={() => handleDetail(project)}>
              <Image
                className={styles.projectCover}
                src={project.cover}
                mode="aspectFill"
                onError={() => console.error('[ProjectPage] 项目封面加载失败', project.id)}
              />
              <View className={styles.projectBody}>
                <View className={styles.projectNameRow}>
                  <Text className={styles.projectName}>{project.name}</Text>
                  <StatusTag text={project.statusLabel || PROJECT_STAGE_LABEL[project.stage]} tone="gold" />
                </View>
                <Text className={styles.spaceName}>{project.spaceName}</Text>
                <View className={styles.stageRow}>
                  {PROJECT_STAGE_ORDER.map((stage, index) => {
                    const done = index < currentIndex;
                    const current = index === currentIndex;
                    return (
                      <View
                        key={stage}
                        className={classnames(
                          styles.stageChip,
                          done && styles.stageChipDone,
                          current && styles.stageChipCurrent
                        )}
                      >
                        <Text
                          className={classnames(
                            styles.stageChipText,
                            done && styles.stageChipTextDone,
                            current && styles.stageChipTextCurrent
                          )}
                        >
                          {PROJECT_STAGE_LABEL[stage]}
                        </Text>
                      </View>
                    );
                  })}
                </View>
                <View className={styles.progressRow}>
                  <View className={styles.progressWrap}>
                    <ProgressBar percent={project.progress} />
                  </View>
                  <Text className={styles.progressText}>{project.progress}%</Text>
                </View>
                <View className={styles.milestoneRow}>
                  <Text className={styles.milestoneText}>下一节点：{project.nextMilestone}</Text>
                  <Text className={styles.milestoneDate}>{project.nextDate}</Text>
                </View>
                <View className={styles.metaRow}>
                  <View className={styles.metaItem}>
                    <Text className={styles.metaLabel}>施工方</Text>
                    <Text className={styles.metaValue}>{project.contractor}</Text>
                  </View>
                  <View className={styles.metaItem}>
                    <Text className={styles.metaLabel}>项目预算</Text>
                    <Text className={styles.metaValue}>{project.budget}</Text>
                  </View>
                </View>
              </View>
            </View>
          );
        })
      ) : (
        <View className={styles.emptyTip}>
          <Text className={styles.emptyTipText}>暂无进行中的改造项目</Text>
        </View>
      )}

      <SectionHeader title="已交付" subtitle="交付即运营起点" />
      {deliveredProjects.length > 0 ? (
        <View className={styles.deliveredCard}>
          {deliveredProjects.map((project) => (
            <View key={project.id} className={styles.deliveredItem} onClick={() => handleDetail(project)}>
              <View className={styles.deliveredMain}>
                <Text className={styles.deliveredName}>{project.name}</Text>
                <Text className={styles.deliveredMeta}>
                  {project.spaceName} · {project.nextMilestone} · {project.nextDate}
                </Text>
              </View>
              <StatusTag text="已交付" tone="green" />
            </View>
          ))}
        </View>
      ) : (
        <View className={styles.emptyTip}>
          <Text className={styles.emptyTipText}>暂无已交付项目</Text>
        </View>
      )}
    </View>
  );
};

export default ProjectPage;