import React, { useState, useCallback } from 'react';
import { View, Text, Image, Button } from '@tarojs/components';
import Taro, { useRouter, usePullDownRefresh, useDidShow } from '@tarojs/taro';
import SectionHeader from '@/components/SectionHeader';
import { callFunction } from '@/services/cloud';
import type {
  ElderlyPackage,
  ElderlyPackagesResult,
  SubsidyEstimate
} from '@/types/elderly';
import styles from './index.module.scss';

const ElderlyDetailPage: React.FC = () => {
  const router = useRouter();
  const routeCode = router.params.id || '';
  const [pkg, setPkg] = useState<ElderlyPackage | null>(null);
  const [disclosure, setDisclosure] = useState<string>('');
  const [estimate, setEstimate] = useState<SubsidyEstimate | null>(null);
  const [estimating, setEstimating] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  const loadPackage = useCallback(async () => {
    try {
      const data = await callFunction<ElderlyPackagesResult>('getElderlyPackages');
      const found =
        data.packages.find((item) => item.code === routeCode) || data.packages[0] || null;
      console.info('[ElderlyDetailPage] 套餐详情加载成功', { routeCode, found: found?.code });
      setPkg(found);
      setDisclosure(data.disclosure);
      setError(found ? '' : '暂无可查看的适老套餐');
    } catch (err) {
      console.error('[ElderlyDetailPage] 套餐详情加载失败', err);
      setError('加载失败，请稍后重试');
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [routeCode]);

  useDidShow(() => {
    loadPackage();
  });

  usePullDownRefresh(() => {
    loadPackage();
  });

  const handleEstimate = async () => {
    if (!pkg || estimating) return;
    setEstimating(true);
    Taro.showLoading({ title: '正在估算…' });
    try {
      const data = await callFunction<SubsidyEstimate>('estimateSubsidy', { packageCode: pkg.code });
      console.info('[ElderlyDetailPage] 补贴预估完成', pkg.code, data.minLabel, data.maxLabel);
      setEstimate(data);
    } catch (err) {
      console.error('[ElderlyDetailPage] 补贴预估失败', err);
      Taro.showToast({ title: '预估失败，请稍后重试', icon: 'none' });
    } finally {
      Taro.hideLoading();
      setEstimating(false);
    }
  };

  if (loading && !pkg) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在加载适老套餐…</Text>
      </View>
    );
  }

  if (error || !pkg) {
    return (
      <View className={styles.page}>
        <View className={styles.errorCard}>
          <Text className={styles.errorText}>{error || '暂无可查看的适老套餐'}</Text>
          <Button className={styles.retryButton} onClick={loadPackage}>
            重新加载
          </Button>
        </View>
      </View>
    );
  }

  return (
    <View className={styles.page}>
      <View className={styles.coverWrap}>
        <Image className={styles.cover} src={pkg.cover} mode='aspectFill' />
        <View className={styles.coverMask} />
        <View className={styles.coverContent}>
          <Text className={styles.coverTitle}>{pkg.name}</Text>
          <Text className={styles.coverSub}>{pkg.tagline}</Text>
        </View>
      </View>

      <View className={styles.priceCard}>
        <View className={styles.priceRow}>
          <Text className={styles.price}>{pkg.priceLabel}</Text>
          <Text className={styles.priceUnit}>{pkg.unit}</Text>
        </View>
        <View className={styles.tagRow}>
          {pkg.tags.map((tag) => (
            <View key={tag} className={styles.tagPill}>
              <Text className={styles.tagText}>{tag}</Text>
            </View>
          ))}
        </View>
      </View>

      <SectionHeader title='适老设计维度' subtitle='只声明套餐实际覆盖的维度' />
      <View className={styles.card}>
        {pkg.designDims.map((dim) => (
          <View key={dim} className={styles.dimRow}>
            <View className={styles.dimDot} />
            <Text className={styles.dimText}>{dim}</Text>
          </View>
        ))}
      </View>

      <SectionHeader title='补贴预估' subtitle='非资格认定 · 以主管部门核定为准' />
      <View className={styles.card}>
        {estimate ? (
          <View>
            <View className={styles.estimateHead}>
              <Text className={styles.estimateRange}>
                {estimate.minLabel} - {estimate.maxLabel}
              </Text>
              <View className={styles.estimateBadge}>
                <Text className={styles.estimateBadgeText}>预估 · 非资格认定</Text>
              </View>
            </View>
            <Text className={styles.estimateBasis}>{estimate.basisNote}</Text>
            {estimate.warnings.map((warning) => (
              <Text key={warning} className={styles.warningItem}>· {warning}</Text>
            ))}
            <Text className={styles.disclaimer}>{estimate.disclaimer}</Text>
          </View>
        ) : (
          <View>
            <Text className={styles.estimateHint}>
              按套餐一口价的典型区间估算，未内置地方官方目录，个人资格不参与判定。
            </Text>
            <Button className={styles.estimateButton} onClick={handleEstimate} disabled={estimating}>
              {estimating ? '正在估算…' : '补贴预估（非资格认定）'}
            </Button>
          </View>
        )}
      </View>

      <View className={styles.notice}>
        <Text className={styles.noticeText}>{disclosure}</Text>
      </View>

      <View className={styles.actions}>
        <Button className={styles.ghostButton} onClick={() => Taro.navigateTo({ url: '/pages/ai-consult/index' })}>
          AI 管家咨询
        </Button>
        <Button className={styles.primaryButton} onClick={() => Taro.switchTab({ url: '/pages/care/index' })}>
          返回套餐列表
        </Button>
      </View>
    </View>
  );
};

export default ElderlyDetailPage;
