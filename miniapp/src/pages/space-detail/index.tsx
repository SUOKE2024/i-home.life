import React, { useState, useCallback } from 'react';
import { View, Text, Image, Button } from '@tarojs/components';
import Taro, { useRouter, usePullDownRefresh, useDidShow } from '@tarojs/taro';
import SectionHeader from '@/components/SectionHeader';
import StatusTag from '@/components/StatusTag';
import ProgressBar from '@/components/ProgressBar';
import { callFunction } from '@/services/cloud';
import { useAppStore } from '@/store/useAppStore';
import { SPACE_STATUS_LABEL, SPACE_STATUS_TONE } from '@/types/space';
import type { Space } from '@/types/space';
import styles from './index.module.scss';

// 就绪度四维满分（与后端 compute_smart_readiness 口径一致）
const READINESS_MAX = { device: 30, sensing: 25, scene: 25, compliance: 20 } as const;
const READINESS_LABEL = {
  device: '设备接入',
  sensing: '感知覆盖',
  scene: '场景编排',
  compliance: '合规就绪'
} as const;

const SpaceDetailPage: React.FC = () => {
  const router = useRouter();
  const routeId = router.params.id || '';
  const currentSpaceId = useAppStore((state) => state.currentSpaceId);
  const [space, setSpace] = useState<Space | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  const loadSpace = useCallback(async () => {
    try {
      const data = await callFunction<{ spaces: Space[] }>('getSpaces');
      const targetId = routeId || currentSpaceId || '';
      const found = data.spaces.find((item) => item.id === targetId) || data.spaces[0] || null;
      console.info('[SpaceDetailPage] 空间详情加载成功', { targetId, found: found?.id });
      setSpace(found);
      setError(found ? '' : '暂无可查看的空间资产');
    } catch (err) {
      console.error('[SpaceDetailPage] 空间详情加载失败', err);
      setError('加载失败，请稍后重试');
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [routeId, currentSpaceId]);

  useDidShow(() => {
    loadSpace();
  });

  usePullDownRefresh(() => {
    loadSpace();
  });

  if (loading && !space) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在加载空间资产…</Text>
      </View>
    );
  }

  if (error || !space) {
    return (
      <View className={styles.page}>
        <View className={styles.errorCard}>
          <Text className={styles.errorText}>{error || '暂无可查看的空间资产'}</Text>
          <Button className={styles.retryButton} onClick={loadSpace}>
            重新加载
          </Button>
        </View>
      </View>
    );
  }

  const totalReadiness =
    space.readiness.device + space.readiness.sensing + space.readiness.scene + space.readiness.compliance;

  return (
    <View className={styles.page}>
      <View className={styles.coverWrap}>
        <Image className={styles.cover} src={space.cover} mode='aspectFill' />
        <View className={styles.coverMask} />
        <View className={styles.coverContent}>
          <Text className={styles.coverTitle}>{space.name}</Text>
          <Text className={styles.coverSub}>{space.city} · {space.formatLabel}</Text>
        </View>
      </View>

      <View className={styles.summaryCard}>
        <View className={styles.summaryHead}>
          <StatusTag text={SPACE_STATUS_LABEL[space.status]} tone={SPACE_STATUS_TONE[space.status]} />
          <View className={styles.scoreWrap}>
            <Text className={styles.scoreValue}>{space.score}</Text>
            <Text className={styles.scoreLabel}>健康分</Text>
          </View>
        </View>
        <View className={styles.metaGrid}>
          <View className={styles.metaItem}>
            <Text className={styles.metaValue}>{space.area}㎡</Text>
            <Text className={styles.metaLabel}>建筑面积</Text>
          </View>
          <View className={styles.metaItem}>
            <Text className={styles.metaValue}>{space.deviceCount}</Text>
            <Text className={styles.metaLabel}>接入设备</Text>
          </View>
          <View className={styles.metaItem}>
            <Text className={styles.metaValue}>{totalReadiness}/100</Text>
            <Text className={styles.metaLabel}>智能就绪度</Text>
          </View>
        </View>
      </View>

      <SectionHeader title='智能就绪度' subtitle='四维评分只统计真实接入数据' />
      <View className={styles.card}>
        {(Object.keys(READINESS_MAX) as Array<keyof typeof READINESS_MAX>).map((key) => {
          const value = space.readiness[key];
          const max = READINESS_MAX[key];
          return (
            <View key={key} className={styles.readinessRow}>
              <View className={styles.readinessHead}>
                <Text className={styles.readinessName}>{READINESS_LABEL[key]}</Text>
                <Text className={styles.readinessValue}>
                  {value}/{max}
                </Text>
              </View>
              <ProgressBar percent={(value / max) * 100} tone='green' />
            </View>
          );
        })}
      </View>

      <SectionHeader title='资产信息' />
      <View className={styles.card}>
        <View className={styles.infoRow}>
          <Text className={styles.infoLabel}>空间业态</Text>
          <Text className={styles.infoValue}>{space.formatLabel}</Text>
        </View>
        <View className={styles.infoRow}>
          <Text className={styles.infoLabel}>所在城市</Text>
          <Text className={styles.infoValue}>{space.city}</Text>
        </View>
        <View className={styles.infoRow}>
          <Text className={styles.infoLabel}>建档时间</Text>
          <Text className={styles.infoValue}>{space.createTime}</Text>
        </View>
        {space.packageCode ? (
          <View className={styles.infoRow}>
            <Text className={styles.infoLabel}>适老套餐</Text>
            <Text className={styles.infoValue}>{space.packageCode}</Text>
          </View>
        ) : null}
      </View>

      <View className={styles.actions}>
        <Button className={styles.ghostButton} onClick={() => Taro.navigateTo({ url: '/pages/ai-consult/index' })}>
          AI 管家咨询
        </Button>
        <Button className={styles.primaryButton} onClick={() => Taro.switchTab({ url: '/pages/smart/index' })}>
          进入智能控制
        </Button>
      </View>
    </View>
  );
};

export default SpaceDetailPage;
