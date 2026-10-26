import React, { useState, useCallback } from 'react';
import { View, Text, Input, Textarea, Button, Picker } from '@tarojs/components';
import Taro, { useRouter } from '@tarojs/taro';
import SectionHeader from '@/components/SectionHeader';
import { callFunction } from '@/services/cloud';
import { track } from '@/services/api';
import styles from './index.module.scss';

/**
 * 提交改造需求（业主自建项目）。
 *
 * 为什么要有这一页：小程序此前是纯只读的 —— 业主看完套餐只能返回，留不下任何线索。
 * 后端 `POST /api/projects` 对任意登录用户开放，提交后项目立即出现在「项目」tab，
 * 派单、勘测、报价都挂在同一个 project_id 上，这条链路才闭合。
 *
 * 诚实边界：
 *  - 写操作不降级演示数据（见 services/cloud.ts），失败会明确报错，不假装成功；
 *  - 手机号在未完成微信认证前无法一键获取，因此这里用手填（不依赖 getPhoneNumber），
 *    但只用于上门勘测联系，不做营销触达。
 */

interface ProjectTypeOption {
  code: string;
  label: string;
}

/** 与后端 ProjectCreate.project_type 枚举一一对应，不自造值 */
const PROJECT_TYPES: ProjectTypeOption[] = [
  { code: 'full_renovation', label: '全屋改造' },
  { code: 'hard_decoration', label: '硬装施工' },
  { code: 'soft_furnishing', label: '软装搭配' },
  { code: 'kitchen', label: '厨房改造' },
  { code: 'bathroom', label: '卫生间改造' },
  { code: 'curtain', label: '窗帘定制' },
  { code: 'electrical', label: '水电改造' },
  { code: 'carpentry', label: '木工定制' },
  { code: 'painting', label: '油漆涂装' },
  { code: 'plumbing', label: '管道改造' },
  { code: 'masonry', label: '泥瓦工程' },
  { code: 'installation', label: '安装服务' }
];

const PHONE_PATTERN = /^1[3-9]\d{9}$/;

const DemandPage: React.FC = () => {
  const router = useRouter();
  const presetPackage = router.params.packageName
    ? decodeURIComponent(router.params.packageName)
    : '';
  const presetType = router.params.projectType || '';

  const [name, setName] = useState<string>('');
  const [typeIndex, setTypeIndex] = useState<number>(
    Math.max(PROJECT_TYPES.findIndex((item) => item.code === presetType), 0)
  );
  const [area, setArea] = useState<string>('');
  const [address, setAddress] = useState<string>('');
  const [contactName, setContactName] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [description, setDescription] = useState<string>(
    presetPackage ? `意向套餐：${presetPackage}` : ''
  );
  const [submitting, setSubmitting] = useState<boolean>(false);

  const handleSubmit = useCallback(async () => {
    if (submitting) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      Taro.showToast({ title: '请填写小区/空间名称', icon: 'none' });
      return;
    }
    const trimmedPhone = phone.trim();
    if (trimmedPhone && !PHONE_PATTERN.test(trimmedPhone)) {
      Taro.showToast({ title: '手机号格式不正确', icon: 'none' });
      return;
    }
    const areaValue = area.trim() ? Number(area.trim()) : NaN;
    if (area.trim() && (!Number.isFinite(areaValue) || areaValue <= 0)) {
      Taro.showToast({ title: '面积请填写数字', icon: 'none' });
      return;
    }

    setSubmitting(true);
    Taro.showLoading({ title: '正在提交…' });
    try {
      const result = await callFunction<{ projectId: string; name: string }>(
        'submitRenovationDemand',
        {
          name: trimmedName,
          projectType: PROJECT_TYPES[typeIndex].code,
          address: address.trim(),
          totalArea: Number.isFinite(areaValue) ? areaValue : undefined,
          description: description.trim(),
          contactName: contactName.trim(),
          contactPhone: trimmedPhone
        }
      );
      track('demand_submitted', { project_type: PROJECT_TYPES[typeIndex].code });
      console.info('[DemandPage] 需求提交成功', result.projectId);
      Taro.hideLoading();
      await Taro.showToast({ title: '需求已提交', icon: 'success' });
      // 回到项目 tab：新项目就在列表首位，用户能立刻看到自己的需求
      Taro.switchTab({ url: '/pages/project/index' });
    } catch (err) {
      Taro.hideLoading();
      const raw = err instanceof Error ? err.message : '提交失败，请稍后重试';
      console.error('[DemandPage] 需求提交失败', err);
      // 「未登录」是平台限制（H5/支付宝/抖音目前没有登录通道），不是用户操作失误，
      // 说清楚该去哪里提交，别让人反复重试。
      const message = /未登录/.test(raw)
        ? '当前环境暂不支持提交需求，请在微信小程序中打开并提交。'
        : raw;
      Taro.showModal({
        title: '提交未完成',
        content: message,
        showCancel: false
      });
    } finally {
      setSubmitting(false);
    }
  }, [
    submitting,
    name,
    phone,
    area,
    typeIndex,
    address,
    description,
    contactName
  ]);

  return (
    <View className={styles.page}>
      <View className={styles.hero}>
        <Text className={styles.heroTitle}>提交改造需求</Text>
        <Text className={styles.heroDesc}>
          提交后进入索克勘测排期，顾问会与你联系确认上门时间
        </Text>
      </View>

      <SectionHeader title="需求信息" subtitle="* 为必填" />

      <View className={styles.formCard}>
        <View className={styles.field}>
          <Text className={styles.label}>
            小区 / 空间名称<Text className={styles.required}>*</Text>
          </Text>
          <Input
            className={styles.input}
            value={name}
            placeholder="如：春城慧谷 3 栋 1202"
            maxlength={60}
            onInput={(event) => setName(event.detail.value)}
          />
        </View>

        <View className={styles.field}>
          <Text className={styles.label}>改造类型</Text>
          <Picker
            mode="selector"
            range={PROJECT_TYPES.map((item) => item.label)}
            value={typeIndex}
            onChange={(event) => setTypeIndex(Number(event.detail.value))}
          >
            <View className={styles.pickerValue}>
              <Text className={styles.pickerText}>{PROJECT_TYPES[typeIndex].label}</Text>
              <Text className={styles.pickerArrow}>›</Text>
            </View>
          </Picker>
        </View>

        <View className={styles.field}>
          <Text className={styles.label}>建筑面积（㎡）</Text>
          <Input
            className={styles.input}
            value={area}
            type="digit"
            placeholder="如：98"
            onInput={(event) => setArea(event.detail.value)}
          />
        </View>

        <View className={styles.field}>
          <Text className={styles.label}>详细地址</Text>
          <Input
            className={styles.input}
            value={address}
            placeholder="用于安排上门勘测，可留空"
            maxlength={120}
            onInput={(event) => setAddress(event.detail.value)}
          />
        </View>
      </View>

      <SectionHeader title="联系方式" subtitle="仅用于勘测与方案沟通" />

      <View className={styles.formCard}>
        <View className={styles.field}>
          <Text className={styles.label}>称呼</Text>
          <Input
            className={styles.input}
            value={contactName}
            placeholder="如：王女士"
            maxlength={20}
            onInput={(event) => setContactName(event.detail.value)}
          />
        </View>

        <View className={styles.field}>
          <Text className={styles.label}>手机号</Text>
          <Input
            className={styles.input}
            value={phone}
            type="number"
            placeholder="便于顾问回电"
            maxlength={11}
            onInput={(event) => setPhone(event.detail.value)}
          />
        </View>

        <View className={styles.field}>
          <Text className={styles.label}>补充说明</Text>
          <Textarea
            className={styles.textarea}
            value={description}
            placeholder="可说明户型、期望工期、预算范围或特别诉求"
            maxlength={300}
            onInput={(event) => setDescription(event.detail.value)}
          />
        </View>
      </View>

      <View className={styles.notice}>
        <Text className={styles.noticeText}>
          提交即表示同意我们就本次需求与你联系。报价以现场勘测与签约合同为准，
          平台不预先承诺价格与工期。
        </Text>
      </View>

      <Button
        className={styles.submitButton}
        loading={submitting}
        disabled={submitting}
        onClick={handleSubmit}
      >
        {submitting ? '正在提交…' : '提交需求，安排勘测'}
      </Button>

      <View className={styles.bottomSpace} />
    </View>
  );
};

export default DemandPage;
