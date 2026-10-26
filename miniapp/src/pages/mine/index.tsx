import React, { useState, useCallback } from 'react';
import { View, Text, Image, Button } from '@tarojs/components';
import Taro, { usePullDownRefresh, useDidShow } from '@tarojs/taro';
import SectionHeader from '@/components/SectionHeader';
import DataSourceBadge from '@/components/DataSourceBadge';
import { callFunction, invalidateCache } from '@/services/cloud';
import { bindPhone, logout } from '@/services/session';
import { useAppStore } from '@/store/useAppStore';
import { CLIENT_VERSION } from '@/config/env';
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
  const [binding, setBinding] = useState<boolean>(false);
  const setUser = useAppStore((state) => state.setUser);
  const sessionPhase = useAppStore((state) => state.sessionPhase);

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
    invalidateCache();
    loadProfile();
  });

  /** 手机号快速验证：微信原生 getPhoneNumber 回传 code，后端换号并绑定 */
  const handleGetPhoneNumber = async (event: any) => {
    const detail = event?.detail || {};
    const code = detail.code as string | undefined;
    if (!code) {
      // 未完成微信认证的小程序拿不到 getPhoneNumber 权限，微信只回 errMsg 不含 code，
      // 与「用户主动取消」必须分开提示，否则用户会以为是自己点错了。
      const errMsg = String(detail.errMsg || '');
      if (/no permission/i.test(errMsg)) {
        Taro.showModal({
          title: '暂时无法验证手机号',
          content: '当前小程序尚未完成微信认证，「手机号快速验证」能力未开通。认证通过后即可一键绑定。',
          showCancel: false
        });
      } else {
        Taro.showToast({ title: '你已取消手机号授权', icon: 'none' });
      }
      return;
    }
    setBinding(true);
    Taro.showLoading({ title: '正在绑定…' });
    try {
      await bindPhone(code);
      await loadProfile();
      Taro.showToast({ title: '手机号绑定成功', icon: 'success' });
    } catch (err) {
      console.error('[MinePage] 手机号绑定失败', err);
      Taro.showToast({
        title: err instanceof Error ? err.message : '绑定失败，请稍后重试',
        icon: 'none'
      });
    } finally {
      Taro.hideLoading();
      setBinding(false);
    }
  };

  const handleLogout = () => {
    Taro.showModal({
      title: '退出登录',
      content: '退出后将以访客身份浏览，空间与项目数据需重新登录查看。',
      confirmText: '退出',
      success: async (res) => {
        if (!res.confirm) return;
        await logout();
        invalidateCache();
        await loadProfile();
        Taro.showToast({ title: '已退出登录', icon: 'none' });
      }
    });
  };

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
          key: 'privacy',
          badge: '私',
          title: '隐私保护指引',
          desc: '信息收集范围与使用说明',
          onTap: () => Taro.navigateTo({ url: '/pages/agreement/index?type=privacy' })
        },
        {
          key: 'terms',
          badge: '约',
          title: '用户服务协议',
          desc: '服务边界与责任说明',
          onTap: () => Taro.navigateTo({ url: '/pages/agreement/index?type=terms' })
        },
        {
          key: 'about',
          badge: '关',
          title: '关于索克家居',
          desc: '空间健康资产运营商',
          onTap: () =>
            Taro.showToast({
              title: `索克家居小程序 v${CLIENT_VERSION} · 空间健康资产运营商`,
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

  const phone = overview?.user.phone || '';
  const needBindPhone = process.env.TARO_ENV === 'weapp' && !phone;

  return (
    <View className={styles.page}>
      <View className={styles.hero}>
        <View className={styles.userRow}>
          {overview?.user.avatar ? (
            <Image
              className={styles.avatar}
              src={overview.user.avatar}
              mode="aspectFill"
              onError={() => console.error('[MinePage] 头像加载失败')}
            />
          ) : (
            <View className={styles.avatarFallback}>
              <Text className={styles.avatarFallbackText}>
                {(overview?.user.nickname || '索').slice(0, 1)}
              </Text>
            </View>
          )}
          <View className={styles.userInfo}>
            <Text className={styles.nickname}>{overview?.user.nickname ?? '索克业主'}</Text>
            <View className={styles.userMeta}>
              {needBindPhone ? (
                <Button
                  className={styles.bindPhoneBtn}
                  openType="getPhoneNumber"
                  onGetPhoneNumber={handleGetPhoneNumber}
                  loading={binding}
                  disabled={binding}
                >
                  绑定手机号
                </Button>
              ) : (
                <Text className={styles.phone}>{phone || '未绑定手机号'}</Text>
              )}
              <View className={styles.roleTag}>
                <Text className={styles.roleTagText}>{overview?.user.roleLabel ?? '业主'}</Text>
              </View>
            </View>
            <Text className={styles.joinText}>
              {sessionPhase === 'authenticated'
                ? `会员始于 ${overview?.user.memberSince || '—'}`
                : '访客浏览模式'}
            </Text>
            <DataSourceBadge className={styles.sourceBadge} verbose />
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
            <Text className={styles.statLabel}>设备接入</Text>
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

        <View className={styles.logoutWrap}>
          {process.env.TARO_ENV === 'weapp' ? (
            <Button className={styles.serviceBtn} openType='contact'>
              联系客服
            </Button>
          ) : null}
          {sessionPhase === 'authenticated' ? (
            <Button className={styles.logoutBtn} onClick={handleLogout}>
              退出登录
            </Button>
          ) : null}
        </View>

        <View className={styles.footer}>
          <Text className={styles.footerText}>索克家居小程序 v{CLIENT_VERSION}</Text>
          <Text className={styles.footerSlogan}>空间健康资产运营商 · 一次改造交付，长期健康运营</Text>
        </View>
      </View>
    </View>
  );
};

export default MinePage;
