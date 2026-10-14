import React, { useState, useCallback } from 'react';
import { View, Text, ScrollView } from '@tarojs/components';
import Taro, { usePullDownRefresh, useDidShow } from '@tarojs/taro';
import classnames from 'classnames';
import SectionHeader from '@/components/SectionHeader';
import StatusTag from '@/components/StatusTag';
import type { StatusTone } from '@/components/StatusTag';
import { callFunction } from '@/services/cloud';
import { useAppStore } from '@/store/useAppStore';
import type { SmartDevice } from '@/types/device';
import type { ExecuteSceneResult, SceneAutomation, SceneType } from '@/types/scene';
import type { HealthRecordsResult } from '@/types/health';
import type { Space } from '@/types/space';
import styles from './index.module.scss';

const SCENE_TYPE_TONE: Record<SceneType, StatusTone> = {
  manual: 'gray',
  scheduled: 'gold',
  triggered: 'blue',
  geo: 'green'
};

const shortSpaceName = (name: string): string => name.split(' · ').pop() ?? name;

const SmartPage: React.FC = () => {
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [devices, setDevices] = useState<SmartDevice[]>([]);
  const [scenes, setScenes] = useState<SceneAutomation[]>([]);
  const [health, setHealth] = useState<HealthRecordsResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [controllingId, setControllingId] = useState<string | null>(null);
  const currentSpaceId = useAppStore((state) => state.currentSpaceId);
  const setCurrentSpace = useAppStore((state) => state.setCurrentSpace);

  const loadSpaceDetail = useCallback(async (spaceId: string) => {
    const [deviceRes, sceneRes] = await Promise.all([
      callFunction<{ devices: SmartDevice[] }>('getDevices', { spaceId }),
      callFunction<{ scenes: SceneAutomation[] }>('getScenes', { spaceId })
    ]);
    setDevices(deviceRes.devices);
    setScenes(sceneRes.scenes);
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [spaceRes, healthRes] = await Promise.all([
        callFunction<{ spaces: Space[] }>('getSpaces'),
        callFunction<HealthRecordsResult>('getHealthRecords')
      ]);
      setSpaces(spaceRes.spaces);
      setHealth(healthRes);
      const activeId = useAppStore.getState().currentSpaceId ?? spaceRes.spaces[0]?.id ?? null;
      if (activeId) {
        if (!useAppStore.getState().currentSpaceId) {
          setCurrentSpace(activeId);
        }
        await loadSpaceDetail(activeId);
      }
      console.info('[SmartPage] 智控数据加载成功', { spaces: spaceRes.spaces.length });
    } catch (err) {
      console.error('[SmartPage] 智控数据加载失败', err);
      Taro.showToast({ title: '加载失败，请稍后重试', icon: 'none' });
    } finally {
      setLoading(false);
      Taro.stopPullDownRefresh();
    }
  }, [loadSpaceDetail, setCurrentSpace]);

  useDidShow(() => {
    loadAll();
  });

  usePullDownRefresh(() => {
    loadAll();
  });

  const handleSpaceChange = async (spaceId: string) => {
    if (spaceId === currentSpaceId) return;
    setCurrentSpace(spaceId);
    console.info('[SmartPage] 切换空间', spaceId);
    try {
      await loadSpaceDetail(spaceId);
    } catch (err) {
      console.error('[SmartPage] 空间设备加载失败', err);
      Taro.showToast({ title: '空间数据加载失败', icon: 'none' });
    }
  };

  const handleToggleDevice = async (device: SmartDevice) => {
    if (!device.switchable || controllingId === device.id) return;
    setControllingId(device.id);
    try {
      const res = await callFunction<{ device: SmartDevice }>('controlDevice', {
        deviceId: device.id,
        action: 'toggle'
      });
      setDevices((prev) => prev.map((item) => (item.id === res.device.id ? res.device : item)));
      Taro.showToast({
        title: `${res.device.name}已${res.device.status === 'on' ? '开启' : '关闭'}`,
        icon: 'none'
      });
    } catch (err) {
      console.error('[SmartPage] 设备控制失败', err);
      Taro.showToast({ title: err instanceof Error ? err.message : '设备控制失败', icon: 'none' });
    } finally {
      setControllingId(null);
    }
  };

  const handleExecuteScene = async (scene: SceneAutomation) => {
    if (!scene.enabled) {
      Taro.showToast({ title: '该场景已停用', icon: 'none' });
      return;
    }
    try {
      const res = await callFunction<ExecuteSceneResult>('executeScene', { sceneId: scene.id });
      console.info('[SmartPage] 场景执行成功', res.sceneId);
      setScenes((prev) =>
        prev.map((item) => (item.id === scene.id ? { ...item, lastExecutedAt: '刚刚' } : item))
      );
      Taro.showToast({ title: `「${scene.name}」已执行`, icon: 'none' });
    } catch (err) {
      console.error('[SmartPage] 场景执行失败', err);
      Taro.showToast({ title: err instanceof Error ? err.message : '场景执行失败', icon: 'none' });
    }
  };

  if (loading && spaces.length === 0) {
    return (
      <View className={styles.loading}>
        <Text className={styles.loadingText}>正在连接智能空间…</Text>
      </View>
    );
  }

  return (
    <View className={styles.page}>
      <ScrollView scrollX className={styles.spaceChips}>
        {spaces.map((space) => {
          const active = space.id === currentSpaceId;
          return (
            <View
              key={space.id}
              className={classnames(styles.chip, active && styles.chipActive)}
              onClick={() => handleSpaceChange(space.id)}
            >
              <Text className={classnames(styles.chipText, active && styles.chipTextActive)}>
                {shortSpaceName(space.name)}
              </Text>
            </View>
          );
        })}
      </ScrollView>

      {health ? (
        <View className={styles.healthCard}>
          <View className={styles.healthHeader}>
            <Text className={styles.healthTitle}>健康监测</Text>
            <Text className={styles.healthUpdate}>
              最近更新 {health.records[0]?.recordedAt ?? '—'}
            </Text>
          </View>
          <View className={styles.healthGrid}>
            {health.summary.map((item) => (
              <View key={item.metric} className={styles.healthItem}>
                <View className={styles.healthValueRow}>
                  <Text className={styles.healthValue}>{item.valueText}</Text>
                  <Text className={styles.healthUnit}>{item.unit}</Text>
                </View>
                <Text className={styles.healthLabel}>{item.label}</Text>
              </View>
            ))}
          </View>
          <Text className={styles.disclaimer}>{health.disclaimer}</Text>
        </View>
      ) : null}

      <SectionHeader
        title="设备控制"
        subtitle={`${devices.filter((item) => item.online).length}/${devices.length} 在线`}
      />
      {devices.length > 0 ? (
        <View className={styles.deviceGrid}>
          {devices.map((device) => (
            <View
              key={device.id}
              className={classnames(styles.deviceCard, !device.online && styles.deviceCardOffline)}
              onClick={() => handleToggleDevice(device)}
            >
              <View className={styles.deviceTop}>
                <View className={styles.deviceBadge}>
                  <Text className={styles.deviceBadgeText}>{device.badge}</Text>
                </View>
                {device.switchable ? (
                  <View className={classnames(styles.switchTrack, device.status === 'on' && styles.switchTrackOn)}>
                    <View className={classnames(styles.switchThumb, device.status === 'on' && styles.switchThumbOn)} />
                  </View>
                ) : null}
              </View>
              <Text className={styles.deviceName}>{device.name}</Text>
              <Text className={styles.deviceValue}>{device.valueText}</Text>
              <View className={styles.deviceStatusRow}>
                <View className={classnames(styles.deviceStatusDot, !device.online && styles.deviceStatusDotOff)} />
                <Text className={styles.deviceStatusText}>
                  {device.online ? `${device.room} · ${device.statusText}` : '离线'}
                </Text>
              </View>
            </View>
          ))}
        </View>
      ) : (
        <View className={styles.emptyTip}>
          <Text className={styles.emptyTipText}>该空间暂无接入设备，可先完成智能化改造</Text>
        </View>
      )}

      <SectionHeader title="场景自动化" subtitle={`${scenes.length} 个场景`} />
      {scenes.length > 0 ? (
        <View className={styles.sceneList}>
          {scenes.map((scene) => (
            <View key={scene.id} className={styles.sceneItem}>
              <View className={styles.sceneMain}>
                <View className={styles.sceneNameRow}>
                  <Text className={styles.sceneName}>{scene.name}</Text>
                  <StatusTag text={scene.sceneTypeLabel} tone={SCENE_TYPE_TONE[scene.sceneType]} />
                </View>
                <Text className={styles.sceneMeta}>
                  触发：{scene.trigger} · {scene.actions} · 最近 {scene.lastExecutedAt}
                </Text>
              </View>
              <View
                className={classnames(styles.sceneBtn, !scene.enabled && styles.sceneBtnDisabled)}
                onClick={() => handleExecuteScene(scene)}
              >
                <Text className={styles.sceneBtnText}>执行</Text>
              </View>
            </View>
          ))}
        </View>
      ) : (
        <View className={styles.emptyTip}>
          <Text className={styles.emptyTipText}>该空间暂无自动化场景</Text>
        </View>
      )}
    </View>
  );
};

export default SmartPage;