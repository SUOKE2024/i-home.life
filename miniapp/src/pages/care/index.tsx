import React, { useState, useCallback } from 'react';
import { View, Text, Image } from '@tarojs/components';
import Taro, { usePullDownRefresh, useDidShow } from '@tarojs/taro';
import SectionHeader from '@/components/SectionHeader';
import StatusTag from '@/components/StatusTag';
import { callFunction } from '@/services/cloud';
import type {
  ElderlyPackage,
  ElderlyPackageCode,
  ElderlyPackagesResult,
  SubsidyEstimate
} from '@/types/elderly';
import styles from './index.module.scss';

interface CareFormat {
  key: string;
  badge: string;
  name: string;
  desc: string;
}

const CARE_FORMATS: CareFormat[] = [
  { key: 'herb_food', badge: '膳', name: '药膳庭院', desc: '庭院药膳业态空间改造' },
  { key: 'forest_bath', badge: '浴', name: '森林药浴', desc: '森林药浴小院业态改造' },
  { key: 'study', badge: '学', name: '康养研学', desc: '康养研学空间业态改造' },
  { key: 'stay', badge: '居', name: '季节旅居', desc: '季节性旅居空间改造' }
];

const CarePage: React.FC = () => {
  const [result, setResult] = useState<ElderlyPackagesResult | null>(null);
  const [estimates, setEstimates] = useState<Record<string, SubsidyEstimate>>({});
  const [estimatingCode, setEstimatingCode] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadPackages = useCallback(async () => {
    try {
      const data = await callFunction<ElderlyPackagesResult>('getElderlyPackages');
      console.info('[CarePage] 适老套餐加载成功', { count: data.packages.length });
      setResult(data);
    } catch (err) {
      console.error('[CarePage] 适老套餐加载失败', err);
      Taro.showToast({ title: '加载失败，请稍后重试', icon: 'none' });
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, []);

  useDidShow(() => {
    loadPackages();
  });

  usePullDownRefresh(() => {
    loadPackages();
  });

  const handleEstimate = async (code: ElderlyPackageCode) => {
    if (estimates[code] || estimatingCode) return;
    setEstimatingCode(code);
    Taro.showLoading({ title: '正在估算…' });
    try {
      const data = await callFunction<SubsidyEstimate>('estimateSubsidy', { packageCode: code });
      console.info('[CarePage] 补贴预估完成', code, data.minLabel, data.maxLabel);
      setEstimates((prev) => ({ ...prev, [code]: data }));
    } catch (err) {
      console.error('[CarePage] 补贴预估失败', err);
      Taro.showToast({ title: '预估失败，请稍后重试', icon: 'none' });
    } finally {
      Taro.hideLoading();
      setEstimatingCode(null);
    }
  };

  const handleDetail = (pkg: ElderlyPackage) => {
    console.info('[CarePage] 查看套餐详情', pkg.code);
    Taro.navigateTo({ url: '/pages/elderly-detail/index' });
  };

  const handleFormatTap = (format: CareFormat) => {
    console.info('[CarePage] 康养业态服务咨询', format.key);
    Taro.navigateTo({ url: '/pages/ai-consult/index' });
  };

  if (loading && !result) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在加载康养服务…</Text>
      </View>
    );
  }

  return (
    <View className={styles.page}>
      <View className={styles.hero}>
        <Text className={styles.heroTitle}>适老改造 · 安心之选</Text>
        <Text className={styles.heroDesc}>
          一口价 · 干法施工 · 0 搬家，改造完成后可持续接入智能守护与健康监测
        </Text>
        <View className={styles.heroTags}>
          <View className={styles.heroTag}>
            <Text className={styles.heroTagText}>对接适老供给方向</Text>
          </View>
          <View className={styles.heroTag}>
            <Text className={styles.heroTagText}>补贴预估工具</Text>
          </View>
        </View>
      </View>

      <SectionHeader title="适老改造套餐" subtitle={`${result?.packages.length ?? 0} 款一口价`} />
      {result?.packages.map((pkg) => {
        const estimate = estimates[pkg.code];
        return (
          <View key={pkg.code} className={styles.pkgCard}>
            <Image
              className={styles.pkgCover}
              src={pkg.cover}
              mode="aspectFill"
              onError={() => console.error('[CarePage] 套餐封面加载失败', pkg.code)}
            />
            <View className={styles.pkgBody}>
              <View className={styles.pkgNameRow}>
                <Text className={styles.pkgName}>{pkg.name}</Text>
                <StatusTag text="一口价" tone="gold" />
              </View>
              <Text className={styles.pkgTagline}>{pkg.tagline}</Text>
              <View className={styles.priceRow}>
                <Text className={styles.price}>{pkg.priceLabel}</Text>
                <Text className={styles.priceUnit}>{pkg.unit}</Text>
              </View>
              <View className={styles.tagRow}>
                {pkg.tags.map((tag) => (
                  <View key={tag} className={styles.tagPill}>
                    <Text className={styles.tagPillText}>{tag}</Text>
                  </View>
                ))}
              </View>
              <View className={styles.dimRow}>
                <Text className={styles.dimLabel}>适老设计维度</Text>
                {pkg.designDims.map((dim) => (
                  <View key={dim} className={styles.dimChip}>
                    <Text className={styles.dimChipText}>{dim}</Text>
                  </View>
                ))}
              </View>
              <View className={styles.actionRow}>
                <View className={styles.btnGhost} onClick={() => handleDetail(pkg)}>
                  <Text className={styles.btnGhostText}>查看详情</Text>
                </View>
                <View className={styles.btnPrimary} onClick={() => handleEstimate(pkg.code)}>
                  <Text className={styles.btnPrimaryText}>补贴预估（非资格认定）</Text>
                </View>
              </View>
              {estimate ? (
                <View className={styles.subsidyPanel}>
                  <View className={styles.subsidyHeader}>
                    <Text className={styles.subsidyTitle}>补贴预估区间</Text>
                    <StatusTag text="预估 · 非资格认定" tone="orange" />
                  </View>
                  <View className={styles.subsidyRange}>
                    <Text className={styles.subsidyValue}>{estimate.minLabel}</Text>
                    <Text className={styles.subsidyDash}>–</Text>
                    <Text className={styles.subsidyValue}>{estimate.maxLabel}</Text>
                  </View>
                  <Text className={styles.subsidyBasis}>{estimate.basisNote}</Text>
                  {estimate.warnings.map((warning) => (
                    <Text key={warning} className={styles.subsidyWarning}>
                      · {warning}
                    </Text>
                  ))}
                  <Text className={styles.subsidyDisclaimer}>{estimate.disclaimer}</Text>
                </View>
              ) : null}
            </View>
          </View>
        );
      })}
      {result ? <Text className={styles.disclosure}>{result.disclosure}</Text> : null}

      <SectionHeader title="康养业态服务" subtitle="改造后可持续运营" />
      <View className={styles.formatsGrid}>
        {CARE_FORMATS.map((format) => (
          <View key={format.key} className={styles.formatCard} onClick={() => handleFormatTap(format)}>
            <View className={styles.formatTop}>
              <View className={styles.formatBadge}>
                <Text className={styles.formatBadgeText}>{format.badge}</Text>
              </View>
              <Text className={styles.formatName}>{format.name}</Text>
            </View>
            <Text className={styles.formatDesc}>{format.desc}</Text>
          </View>
        ))}
      </View>

      <Text className={styles.pageNote}>
        健康监测仅作日常提醒，非医疗诊断；补贴预估非资格认定，均以主管部门与签约合同为准。
      </Text>
    </View>
  );
};

export default CarePage;