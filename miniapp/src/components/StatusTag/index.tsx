import React from 'react';
import { View, Text } from '@tarojs/components';
import classnames from 'classnames';
import styles from './index.module.scss';

export type StatusTone = 'gold' | 'green' | 'blue' | 'orange' | 'red' | 'gray';

interface StatusTagProps {
  text: string;
  tone?: StatusTone;
}

const StatusTag: React.FC<StatusTagProps> = ({ text, tone = 'gray' }) => (
  <View className={classnames(styles.tag, styles[tone])}>
    <Text className={styles.tagText}>{text}</Text>
  </View>
);

export default StatusTag;