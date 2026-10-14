import React from 'react';
import { View, Text } from '@tarojs/components';
import styles from './index.module.scss';

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  extraText?: string;
  onExtraClick?: () => void;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ title, subtitle, extraText, onExtraClick }) => (
  <View className={styles.header}>
    <View className={styles.left}>
      <Text className={styles.title}>{title}</Text>
      {subtitle ? <Text className={styles.subtitle}>{subtitle}</Text> : null}
    </View>
    {extraText ? (
      <View className={styles.extra} onClick={onExtraClick}>
        <Text className={styles.extraText}>{extraText}</Text>
        <Text className={styles.chevron}>›</Text>
      </View>
    ) : null}
  </View>
);

export default SectionHeader;