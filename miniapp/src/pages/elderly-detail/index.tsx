import React from 'react';
import { View, Text } from '@tarojs/components';
import styles from './index.module.scss';

const ElderlyDetailPage: React.FC = () => (
  <View className={styles.page}>
    <View className={styles.icon}>
      <Text className={styles.iconText}>套</Text>
    </View>
    <Text className={styles.title}>套餐详情功能</Text>
    <Text className={styles.desc}>功能正在开发中...</Text>
  </View>
);

export default ElderlyDetailPage;