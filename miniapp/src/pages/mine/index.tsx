import React, { useState, useCallback } from 'react';
import { View, Text, Image } from '@tarojs/components';
import Taro, { usePullDownRefresh, useDidShow } from '@tarojs/taro';
import SectionHeader from '@/components/SectionHeader';
import { callFunction } from '@/services/cloud';
import { useAppStore } from '@/store/useAppStore';
import type { HomeOverview } from '@/types/user';
import styles from './index.module.scss';

interface MenuItem {
  key: string;
  badge: string;
  title: string;
  desc: string;
  onTap: () => void;
}

interface MenuGroup {
  title: string;
  items: MenuItem[];
}

const MinePage: React.FC = () => {
  const [overview, setOverview] = useState<HomeOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const setUser = useAppStore((state) => state.setUser);

  const loadProfile = useCallback(async () => {
    try {
      const data = await callFunction<HomeOverview>('getHomeOverview');
      console.info('[MinePage] 用户档案加载成功', data.user.id);
      setOverview(data);
      setUser(data.user);
    } catch (err) {
      console.error('[MinePage] 用户档案加载失败', err);
      Taro.showToast({ title: '加载失败，请稍后重试', icon: 'none' });
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [setUser]);

  useDidShow(() => {
    loadProfile();
  });

  usePullDownRefresh(() => {
    loadProfile();
  });

  const MENU_GROUPS: MenuGroup[] = [
    {
      title: '我的服务',
      items: [
        {
          key: 'space',
          badge: '房',
          title: '我的空间',
          desc: '空间资产台账与智能就绪度',
          onTap: () => Taro.navigateTo({ url: '/pages/space-detail/index' })
        },
        {
          key: 'project',
          badge: '项',
          title: '我的项目',
          desc: '改造进度与交付记录',
          onTap: () => Taro.switchTab({ url: '/pages/project/index' })
        },
        {
          key: 'care',
          badge: '养',
          title: '适老改造服务',
          desc: '套餐目录与补贴预估（非资格认定）',
          onTap: () => Taro.switchTab({ url: '/pages/care/index' })
        },
        {
          key: 'smart',
          badge: '控',
          title: '智能空间',
          desc: '设备控制与场景自动化',
          onTap: () => Taro.switchTab({ url: '/pages/smart/index' })
        }
      ]
    },
    {
      title: '更多',
      items: [
        {
          key: 'ai',
          badge: 'AI',
          title: 'AI 管家',
          desc: '空间与服务智能咨询',
          onTap: () => Taro.navigateTo({ url: '/pages/ai-consult/index' })
        },
        {
          key: 'about',
          badge: '关',
          title: '关于索克家居',
          desc: '空间健康资产运营商',
          onTap: () =>
            Taro.showToast({
              title: '索克家居小程序 v1.0.0 · 空间健康资产运营商',
              icon: 'none',
              duration: 2500
            })
        }
      ]
    }
  ];

  if (loading && !overview) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在加载个人中心…</Text>
      </View>
    );
  }

  return (
    <View className={styles.page}>
      <View className={styles.hero}>
        <View className={styles.userRow}>
          <Image
            className={styles.avatar}
            src={overview?.user.avatar ?? ''}
            mode="aspectFill"
            onError={() => console.error('[MinePage] 头像加载失败')}
          />
          <View className={styles.userInfo}>
            <Text className={styles.nickname}>{overview?.user.nickname ?? '业主'}</Text>
            <View className={styles.userMeta}>
              <Text className={styles.phone}>{overview?.user.phone ?? '—'}</Text>
              <View className={styles.roleTag}>
                <Text className={styles.roleTagText}>{overview?.user.roleLabel ?? '业主'}</Text>
              </View>
            </View>
            <Text className={styles.joinText}>会员始于 {overview?.user.memberSince ?? '—'}</Text>
          </View>
        </View>
      </View>

      <View className={styles.section}>
        <View className={styles.statsCard}>
          <View className={styles.statItem}>
            <Text className={styles.statValue}>{overview?.stats.spaceCount ?? 0}</Text>
            <Text className={styles.statLabel}>空间资产</Text>
          </View>
          <View className={styles.statDivider} />
          <View className={styles.statItem}>
            <Text className={styles.statValue}>
              {overview ? `${overview.stats.deviceOnline}/${overview.stats.deviceTotal}` : '—'}
            </Text>
            <Text className={styles.statLabel}>设备在线</Text>
          </View>
          <View className={styles.statDivider} />
          <View className={styles.statItem}>
            <Text className={styles.statValue}>{overview?.stats.activeProjectCount ?? 0}</Text>
            <Text className={styles.statLabel}>进行中项目</Text>
          </View>
        </View>

        {MENU_GROUPS.map((group) => (
          <View key={group.title}>
            <SectionHeader title={group.title} />
            <View className={styles.menuCard}>
              {group.items.map((item) => (
                <View key={item.key} className={styles.menuItem} onClick={item.onTap}>
                  <View className={styles.menuBadge}>
                    <Text className={styles.menuBadgeText}>{item.badge}</Text>
                  </View>
                  <View className={styles.menuMain}>
                    <Text className={styles.menuTitle}>{item.title}</Text>
                    <Text className={styles.menuDesc}>{item.desc}</Text>
                  </View>
                  <Text className={styles.menuChevron}>›</Text>
                </View>
              ))}
            </View>
          </View>
        ))}

        <View className={styles.footer}>
          <Text className={styles.footerText}>索克家居小程序 v1.0.0</Text>
          <Text className={styles.footerSlogan}>空间健康资产运营商 · 一次改造交付，长期健康运营</Text>
        </View>
      </View>
    </View>
  );
};

export default MinePage;