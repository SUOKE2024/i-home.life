import React from 'react';
import { View } from '@tarojs/components';
import classnames from 'classnames';
import styles from './index.module.scss';

interface ProgressBarProps {
  percent: number;
  tone?: 'gold' | 'green';
}

const ProgressBar: React.FC<ProgressBarProps> = ({ percent, tone = 'gold' }) => {
  const safePercent = Math.max(0, Math.min(100, Math.round(percent)));
  return (
    <View className={styles.track}>
      <View
        className={classnames(styles.fill, tone === 'green' ? styles.fillGreen : styles.fillGold)}
        style={{ width: `${safePercent}%` }}
      />
    </View>
  );
};

export default ProgressBar;