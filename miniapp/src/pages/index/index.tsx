import React, { useState, useCallback } from 'react';
import { View, Text, Image, ScrollView } from '@tarojs/components';
import Taro, { usePullDownRefresh, useDidShow, useShareAppMessage } from '@tarojs/taro';
import classnames from 'classnames';
import SectionHeader from '@/components/SectionHeader';
import StatusTag from '@/components/StatusTag';
import ProgressBar from '@/components/ProgressBar';
import DataSourceBadge from '@/components/DataSourceBadge';
import { callFunction } from '@/services/cloud';
import { useAppStore } from '@/store/useAppStore';
import { SPACE_STATUS_LABEL, SPACE_STATUS_TONE } from '@/types/space';
import { PROJECT_STAGE_LABEL } from '@/types/project';
import type { HomeAlertType, HomeOverview } from '@/types/user';
import styles from './index.module.scss';

interface QuickService {
  key: string;
  badge: string;
  label: string;
  path: string;
  isTab: boolean;
}

const QUICK_SERVICES: QuickService[] = [
  { key: 'smart', badge: '控', label: '智能家居', path: '/pages/smart/index', isTab: true },
  { key: 'care', badge: '养', label: '适老改造', path: '/pages/care/index', isTab: true },
  { key: 'project', badge: '装', label: '装修项目', path: '/pages/project/index', isTab: true },
  { key: 'ai', badge: 'AI', label: 'AI 管家', path: '/pages/ai-consult/index', isTab: false }
];

const ALERT_DOT_CLASS: Record<HomeAlertType, string> = {
  device: styles.dotBlue,
  health: styles.dotGreen,
  project: styles.dotGold,
  service: styles.dotOrange
};

const getGreeting = (): string => {
  const hour = new Date().getHours();
  if (hour < 6) return '夜深了';
  if (hour < 11) return '早上好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  return '晚上好';
};

const HomePage: React.FC = () => {
  const [overview, setOverview] = useState<HomeOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const setUser = useAppStore((state) => state.setUser);
  const setCurrentSpace = useAppStore((state) => state.setCurrentSpace);

  const loadOverview = useCallback(async () => {
    try {
      const data = await callFunction<HomeOverview>('getHomeOverview');
      console.info('[HomePage] 首页数据加载成功', {
        spaces: data.spaces.length,
        alerts: data.alerts.length,
        healthScore: data.healthScore
      });
      setOverview(data);
      setUser(data.user);
      if (!useAppStore.getState().currentSpaceId && data.spaces.length > 0) {
        setCurrentSpace(data.spaces[0].id);
      }
    } catch (err) {
      console.error('[HomePage] 首页数据加载失败', err);
      Taro.showToast({ title: '加载失败，请稍后重试', icon: 'none' });
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [setUser, setCurrentSpace]);

  useDidShow(() => {
    loadOverview();
  });

  usePullDownRefresh(() => {
    loadOverview();
  });

  // 运营入口：分享带来源标识，便于统计拉新渠道
  useShareAppMessage(() => ({
    title: '索克家居 · 空间健康资产运营，一次改造长期守护',
    path: '/pages/index/index?from=share'
  }));

  const handleServiceTap = (service: QuickService) => {
    console.info('[HomePage] 快捷服务点击', service.key);
    if (service.isTab) {
      Taro.switchTab({ url: service.path });
    } else {
      Taro.navigateTo({ url: service.path });
    }
  };

  const handleSpaceTap = (spaceId: string) => {
    setCurrentSpace(spaceId);
    Taro.navigateTo({ url: '/pages/space-detail/index' });
  };

  if (loading && !overview) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在加载空间健康数据…</Text>
      </View>
    );
  }

  return (
    <View className={styles.page}>
      <View className={styles.hero}>
        <View className={styles.heroTop}>
          <View className={styles.greetingWrap}>
            <Text className={styles.greeting}>
              {getGreeting()}，{overview?.user.nickname ?? '业主'}
            </Text>
            <Text className={styles.subGreeting}>您的空间健康运营已就绪</Text>
            <DataSourceBadge className={styles.sourceBadge} />
          </View>
          {overview ? (
            <View
              className={styles.avatarWrap}
              onClick={() => Taro.switchTab({ url: '/pages/mine/index' })}
            >
              <Image
                className={styles.avatar}
                src={overview.user.avatar}
                mode="aspectFill"
                onError={() => console.error('[HomePage] 头像加载失败')}
              />
            </View>
          ) : null}
        </View>

        {overview ? (
          <View className={styles.scoreCard}>
            <View className={styles.scoreLeft}>
              <View className={styles.scoreRow}>
                <Text className={styles.scoreValue}>{overview.healthScore}</Text>
                <Text className={styles.scoreUnit}>分</Text>
              </View>
              <Text className={styles.scoreLabel}>空间健康指数</Text>
              <Text className={styles.scoreCaption}>四维智能就绪度加权</Text>
              {overview.scoreDelta > 0 ? (
                <View className={styles.scoreDelta}>
                  <Text className={styles.deltaText}>较上周 +{overview.scoreDelta}</Text>
                </View>
              ) : null}
            </View>
            <View className={styles.scoreDivider} />
            <View className={styles.scoreRight}>
              <View className={styles.statItem}>
                <Text className={styles.statValue}>
                  {overview.stats.deviceOnline}/{overview.stats.deviceTotal}
                </Text>
                <Text className={styles.statLabel}>设备接入</Text>
              </View>
              <View className={styles.statItem}>
                <Text className={styles.statValue}>{overview.stats.activeProjectCount}</Text>
                <Text className={styles.statLabel}>进行中项目</Text>
              </View>
              <View className={styles.statItem}>
                <Text className={styles.statValue}>{overview.alerts.length}</Text>
                <Text className={styles.statLabel}>今日提醒</Text>
              </View>
            </View>
          </View>
        ) : null}
      </View>

      <View className={styles.demandBanner} onClick={() => Taro.navigateTo({ url: '/pages/demand/index' })}>
        <View className={styles.demandMain}>
          <Text className={styles.demandTitle}>先勘测，再报价</Text>
          <Text className={styles.demandDesc}>提交改造需求 · 顾问 1 个工作日内联系</Text>
        </View>
        <Text className={styles.demandArrow}>›</Text>
      </View>

      {overview ? (
        <View className={styles.section}>
          <SectionHeader title="我的空间" subtitle={`${overview.stats.spaceCount} 处资产`} />
          <ScrollView scrollX className={styles.spaceScroll}>
            {overview.spaces.map((space) => (
              <View key={space.id} className={styles.spaceCard} onClick={() => handleSpaceTap(space.id)}>
                <Image
                  className={styles.spaceCover}
                  src={space.cover}
                  mode="aspectFill"
                  onError={() => console.error('[HomePage] 空间封面加载失败', space.id)}
                />
                <View className={styles.spaceBody}>
                  <Text className={styles.spaceName}>{space.name}</Text>
                  <Text className={styles.spaceMeta}>
                    {space.formatLabel} · {space.city}
                  </Text>
                  <View className={styles.spaceFooter}>
                    <StatusTag
                      text={SPACE_STATUS_LABEL[space.status]}
                      tone={SPACE_STATUS_TONE[space.status]}
                    />
                    <Text className={styles.spaceScore}>就绪 {space.score} 分</Text>
                  </View>
                </View>
              </View>
            ))}
          </ScrollView>
        </View>
      ) : null}

      <View className={styles.section}>
        <SectionHeader title="快捷服务" subtitle="改造 · 运营 · 服务一站直达" />
        <View className={styles.grid}>
          {QUICK_SERVICES.map((service) => (
            <View key={service.key} className={styles.gridItem} onClick={() => handleServiceTap(service)}>
              <View className={styles.gridIcon}>
                <Text className={styles.gridIconText}>{service.badge}</Text>
              </View>
              <Text className={styles.gridLabel}>{service.label}</Text>
            </View>
          ))}
        </View>
      </View>

      {overview?.activeProject ? (
        <View className={styles.section}>
          <SectionHeader title="改造进行中" extraText="全部项目" onExtraClick={() => Taro.switchTab({ url: '/pages/project/index' })} />
          <View className={styles.projectCard} onClick={() => Taro.navigateTo({ url: `/pages/project-detail/index?id=${overview.activeProject?.id || ''}` })}>
            <View className={styles.projectTop}>
              <Text className={styles.projectName}>{overview.activeProject.name}</Text>
              <StatusTag
                text={overview.activeProject.statusLabel || PROJECT_STAGE_LABEL[overview.activeProject.stage]}
                tone="gold"
              />
            </View>
            <View className={styles.projectProgress}>
              <View className={styles.progressWrap}>
                <ProgressBar percent={overview.activeProject.progress} />
              </View>
              <Text className={styles.progressText}>{overview.activeProject.progress}%</Text>
            </View>
            <View className={styles.projectBottom}>
              <Text className={styles.milestone}>下一节点：{overview.activeProject.nextMilestone}</Text>
              <Text className={styles.milestoneDate}>{overview.activeProject.nextDate}</Text>
            </View>
          </View>
        </View>
      ) : null}

      {overview && overview.alerts.length > 0 ? (
        <View className={styles.section}>
          <SectionHeader title="今日提醒" />
          <View className={styles.alerts}>
            {overview.alerts.map((alert) => (
              <View key={alert.id} className={styles.alertItem}>
                <View className={classnames(styles.alertDot, ALERT_DOT_CLASS[alert.type])} />
                <View className={styles.alertBody}>
                  <View className={styles.alertTitleRow}>
                    <Text className={styles.alertTitle}>{alert.title}</Text>
                    <Text className={styles.alertTime}>{alert.time}</Text>
                  </View>
                  <Text className={styles.alertDesc}>{alert.desc}</Text>
                </View>
              </View>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
};

export default HomePage;